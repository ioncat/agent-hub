"""
core/telegram.py — Telegram bot transport layer (aiogram 3.x, long polling).

Responsibilities:
- Start / stop long polling
- Chat ID security filter — single-user (MULTI_USER_ENABLED=false, default) or open
- Text messages → dispatch to router_callback
- Onboarding FSM: /start → name → skill_type → PDF upload → profile saved
- send_message / send_document / send_typing helpers
- Inline keyboard builder + callback dispatch

Not responsible for:
- Business logic (that's router.py / tool files)
- Formatting CV content (that's cv_cover.py / prompts)

Usage (wired in agent.py):
    bot = TelegramBot(
        token=settings.telegram_token,
        allowed_chat_id=settings.telegram_chat_id,
        on_message=router.handle,
        multi_user_enabled=settings.multi_user_enabled,
    )
    await bot.start()   # blocks until stop() called or KeyboardInterrupt
"""

import asyncio
import logging
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from core.onboarding import (
    SKILL_LABELS,
    VALID_SKILL_TYPES,
    OnboardingStates,
    get_or_create_user_by_chat_id,
    parse_pdf,
    synthesise_profile_stub,
)
from db import database

log = logging.getLogger(__name__)

# Max Telegram message length
_MAX_MSG_LEN = 4096

# Type alias for the router callback
OnMessageCallback = Callable[[str], Awaitable[str]]
OnCallbackCallback = Callable[[str, str], Awaitable[None]]  # action, decision


class TelegramBot:
    """Telegram bot transport layer.

    Args:
        token:               Bot API token from @BotFather.
        allowed_chat_id:     Only messages from this chat_id are processed (single-user mode).
                             Ignored when multi_user_enabled=True.
        on_message:          Async callback ``(text: str) -> str`` called for every
                             non-command, non-onboarding text message.
        on_callback:         Async callback ``(action: str, decision: str) -> None``
                             for inline keyboard presses. Optional.
        multi_user_enabled:  When False (default): only allowed_chat_id is accepted.
                             When True: any Telegram user can interact and onboard.
                             See ARCHITECTURE.md — Known Simplifications.
        default_user_id:     user_id for the single allowed user (single-user mode only).
    """

    def __init__(
        self,
        token: str,
        allowed_chat_id: int,
        on_message: OnMessageCallback,
        on_callback: OnCallbackCallback | None = None,
        multi_user_enabled: bool = False,
        default_user_id: int = 1,
    ) -> None:
        self._bot = Bot(token=token)
        self._dp = Dispatcher(storage=MemoryStorage())
        self._allowed_chat_id = allowed_chat_id
        self._on_message = on_message
        self._on_callback = on_callback
        self._multi_user_enabled = multi_user_enabled
        self._default_user_id = default_user_id
        self._polling_task: asyncio.Task | None = None

        self._register_handlers()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start long polling. Blocks until stop() is called."""
        log.info(
            "TelegramBot: starting long polling (allowed_chat_id=%d, multi_user=%s)",
            self._allowed_chat_id,
            self._multi_user_enabled,
        )
        await self._dp.start_polling(self._bot, handle_signals=False)

    async def stop(self) -> None:
        """Gracefully stop polling and close bot session."""
        log.info("TelegramBot: stopping")
        await self._dp.stop_polling()
        await self._bot.session.close()

    # ── Send helpers ──────────────────────────────────────────────────────────

    async def send_message(
        self,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        parse_mode: str = ParseMode.HTML,
    ) -> None:
        """Send text message to allowed_chat_id.

        Automatically splits messages longer than 4096 chars.
        """
        chunks = _split_message(text)
        for i, chunk in enumerate(chunks):
            markup = reply_markup if i == len(chunks) - 1 else None
            await self._bot.send_message(
                self._allowed_chat_id,
                chunk,
                reply_markup=markup,
                parse_mode=parse_mode,
            )

    async def send_document(
        self,
        file_path: Path,
        caption: str | None = None,
    ) -> None:
        """Send a file (CV PDF, analysis Markdown, etc.) to allowed_chat_id."""
        await self._bot.send_document(
            self._allowed_chat_id,
            FSInputFile(file_path),
            caption=caption,
        )

    async def send_typing(self) -> None:
        """Send 'typing…' chat action while processing."""
        await self._bot.send_chat_action(self._allowed_chat_id, ChatAction.TYPING)

    # ── Keyboard helpers ──────────────────────────────────────────────────────

    @staticmethod
    def build_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
        """Build a Yes / No inline keyboard.

        Callback data format: ``{action}:yes`` / ``{action}:no``
        """
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да",  callback_data=f"{action}:yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"{action}:no"),
        ]])

    @staticmethod
    def _build_skill_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📊 Product Manager (PM)", callback_data="onboard_skill:pm"),
            InlineKeyboardButton(text="🔧 Generic / Other",      callback_data="onboard_skill:generic"),
        ]])

    # ── User ID resolution ────────────────────────────────────────────────────

    async def _resolve_user_id(self, chat_id: int) -> int:
        """Return user_id for a given chat_id.

        Single-user mode: always returns default_user_id.
        Multi-user mode: looks up or creates a user record by telegram_chat_id.
        """
        if self._multi_user_enabled:
            return await get_or_create_user_by_chat_id(chat_id)
        return self._default_user_id

    # ── Handler registration ──────────────────────────────────────────────────

    def _register_handlers(self) -> None:
        dp = self._dp

        # ── /start — onboarding check ──────────────────────────────────────────

        @dp.message(Command("start"))
        async def cmd_start(message: Message, state: FSMContext) -> None:
            if not self._is_allowed(message):
                return
            user_id = await self._resolve_user_id(message.chat.id)
            row = await database.get_user_by_id(user_id)
            has_profile = row is not None and row["profile_json"] is not None

            if has_profile:
                name = row["name"] or "кандидат"
                await message.answer(
                    f"👋 С возвращением, <b>{name}</b>!\n\n"
                    "Отправь ссылку на вакансию — запущу CV-пайплайн.\n"
                    "Или /update_profile чтобы обновить профиль.",
                    parse_mode=ParseMode.HTML,
                )
            else:
                await state.set_state(OnboardingStates.awaiting_name)
                await database.update_user_onboarding_step(user_id, "awaiting_name")
                await message.answer(
                    "👋 Привет! Я <b>Career Agent</b> — помогу найти работу мечты.\n\n"
                    "Сначала нужно создать твой профиль.\n\n"
                    "<b>Как тебя зовут?</b> (имя и фамилия)",
                    parse_mode=ParseMode.HTML,
                )

        # ── /update_profile — re-run onboarding ───────────────────────────────

        @dp.message(Command("update_profile"))
        async def cmd_update_profile(message: Message, state: FSMContext) -> None:
            if not self._is_allowed(message):
                return
            await state.set_state(OnboardingStates.awaiting_name)
            user_id = await self._resolve_user_id(message.chat.id)
            await database.update_user_onboarding_step(user_id, "awaiting_name")
            await message.answer(
                "🔄 <b>Обновление профиля</b>\n\nКак тебя зовут?",
                parse_mode=ParseMode.HTML,
            )

        # ── /set_skill — change skill_type ────────────────────────────────────

        @dp.message(Command("set_skill"))
        async def cmd_set_skill(message: Message) -> None:
            if not self._is_allowed(message):
                return
            await message.answer(
                "Выбери тип роли:",
                reply_markup=self._build_skill_keyboard(),
            )

        # ── FSM step: name ────────────────────────────────────────────────────

        @dp.message(OnboardingStates.awaiting_name, F.text)
        async def onboard_name(message: Message, state: FSMContext) -> None:
            if not self._is_allowed(message):
                return
            name = (message.text or "").strip()
            if not name:
                await message.answer("Пожалуйста, введи имя.")
                return
            await state.update_data(name=name)
            await state.set_state(OnboardingStates.awaiting_skill)
            user_id = await self._resolve_user_id(message.chat.id)
            await database.update_user_onboarding_step(user_id, "awaiting_skill")
            await message.answer(
                f"Приятно познакомиться, <b>{name}</b>!\n\nКакой тип роли тебя интересует?",
                reply_markup=self._build_skill_keyboard(),
                parse_mode=ParseMode.HTML,
            )

        # ── FSM step: skill_type (inline keyboard callback) ───────────────────

        @dp.callback_query(F.data.startswith("onboard_skill:"))
        async def onboard_skill(query: CallbackQuery, state: FSMContext) -> None:
            if query.message and not self._is_allowed_chat(query.message.chat.id):
                await query.answer()
                return
            skill_type = (query.data or "").split(":", 1)[-1]
            if skill_type not in VALID_SKILL_TYPES:
                skill_type = "generic"
            await query.answer()
            await state.update_data(skill_type=skill_type)
            await state.set_state(OnboardingStates.awaiting_pdf)
            user_id = await self._resolve_user_id(query.message.chat.id)  # type: ignore[union-attr]
            await database.update_user_onboarding_step(user_id, "awaiting_pdf")
            label = SKILL_LABELS.get(skill_type, skill_type)
            await query.message.answer(  # type: ignore[union-attr]
                f"Отлично — <b>{label}</b>.\n\n"
                "Теперь загрузи своё <b>CV в формате PDF</b>.\n"
                "Буду читать его и строить твой профиль.",
                parse_mode=ParseMode.HTML,
            )

        # ── /set_skill inline callback (outside onboarding FSM) ───────────────

        @dp.callback_query(F.data.startswith("set_skill:"))
        async def set_skill_callback(query: CallbackQuery) -> None:
            if query.message and not self._is_allowed_chat(query.message.chat.id):
                await query.answer()
                return
            skill_type = (query.data or "").split(":", 1)[-1]
            if skill_type not in VALID_SKILL_TYPES:
                await query.answer("Неизвестный тип роли.")
                return
            user_id = await self._resolve_user_id(query.message.chat.id)  # type: ignore[union-attr]
            await database.update_user_skill_type(user_id, skill_type)
            label = SKILL_LABELS.get(skill_type, skill_type)
            await query.answer(f"Тип роли обновлён: {label}")
            await query.message.answer(  # type: ignore[union-attr]
                f"✅ Тип роли изменён на <b>{label}</b>. Вступит в силу при следующем запуске пайплайна.",
                parse_mode=ParseMode.HTML,
            )

        # ── FSM step: PDF upload ───────────────────────────────────────────────

        @dp.message(OnboardingStates.awaiting_pdf, F.document)
        async def onboard_pdf(message: Message, state: FSMContext) -> None:
            if not self._is_allowed(message):
                return
            doc = message.document
            if doc is None or doc.mime_type != "application/pdf":
                await message.answer("Пожалуйста, отправь PDF-файл (.pdf).")
                return

            await message.answer("⏳ Читаю PDF...")

            # Download to temp file
            tmp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                await self._bot.download(doc, destination=tmp_path)

                # Parse PDF
                try:
                    cv_text = await asyncio.get_event_loop().run_in_executor(
                        None, parse_pdf, tmp_path
                    )
                except (ValueError, RuntimeError) as exc:
                    await message.answer(
                        f"⚠️ Не удалось прочитать PDF: {exc}\n\n"
                        "Попробуй другой файл или вставь текст CV напрямую."
                    )
                    return

                # Resolve user + state data
                data = await state.get_data()
                name = data.get("name", "Candidate")
                skill_type = data.get("skill_type", "pm")
                user_id = await self._resolve_user_id(message.chat.id)

                # Persist to DB
                await database.upsert_user(user_id=user_id, name=name, skill_type=skill_type)
                profile_json = await asyncio.get_event_loop().run_in_executor(
                    None, synthesise_profile_stub, cv_text, name, skill_type
                )
                await database.update_user_profile(user_id, profile_json)
                await database.update_user_onboarding_step(user_id, None)

                await state.clear()

                await message.answer(
                    f"✅ <b>Профиль создан!</b>\n\n"
                    f"Имя: <b>{name}</b>\n"
                    f"Тип роли: <b>{SKILL_LABELS.get(skill_type, skill_type)}</b>\n"
                    f"CV обработан: {len(cv_text):,} символов\n\n"
                    "⚠️ <i>Интервью-система в разработке — профиль пока из CV напрямую.\n"
                    "Используй /update_profile когда интервью будет готово.</i>\n\n"
                    "Теперь можешь отправлять ссылки на вакансии!",
                    parse_mode=ParseMode.HTML,
                )
                log.info(
                    "Onboarding complete: user_id=%d name=%r skill_type=%s cv_len=%d",
                    user_id, name, skill_type, len(cv_text),
                )

            finally:
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)

        # ── FSM interview step (stub) ──────────────────────────────────────────

        @dp.message(OnboardingStates.interview, F.text)
        async def onboard_interview(message: Message, state: FSMContext) -> None:
            if not self._is_allowed(message):
                return
            # STUB — interview not yet designed
            # See docs/discovery/core-differentiators.md — AI Interview System
            await message.answer(
                "⚠️ <i>Интервью-система в разработке.</i>\n"
                "Пока профиль строится из PDF напрямую. Загрузи CV в PDF.",
                parse_mode=ParseMode.HTML,
            )
            await state.set_state(OnboardingStates.awaiting_pdf)

        # ── Regular text messages ─────────────────────────────────────────────

        @dp.message(F.text)
        async def handle_text(message: Message, state: FSMContext) -> None:
            if not self._is_allowed(message):
                return
            # If user is in onboarding but sends text at wrong step, ignore (FSM handles it)
            current_state = await state.get_state()
            if current_state is not None:
                return
            text = message.text or ""
            log.info("TelegramBot: text from %d: %r", message.chat.id, text[:80])
            await self.send_typing()
            try:
                reply = await self._on_message(text)
            except Exception as exc:
                log.exception("on_message callback raised: %s", exc)
                reply = f"⚠️ Ошибка: {exc}"
            await self.send_message(reply)

        # ── General inline keyboard callbacks ────────────────────────────────

        @dp.callback_query()
        async def handle_callback(query: CallbackQuery) -> None:
            if query.message and not self._is_allowed_chat(query.message.chat.id):
                await query.answer()
                return
            data = query.data or ""
            log.info("TelegramBot: callback %r", data)
            await query.answer()

            # onboard_skill and set_skill are handled by their own handlers above
            if data.startswith(("onboard_skill:", "set_skill:")):
                return

            if ":" in data and self._on_callback:
                action, _, decision = data.partition(":")
                try:
                    await self._on_callback(action, decision)
                except Exception as exc:
                    log.exception("on_callback raised: %s", exc)
                    await self.send_message(f"⚠️ Ошибка обработки: {exc}")

    def _is_allowed(self, message: Message) -> bool:
        return self._is_allowed_chat(message.chat.id)

    def _is_allowed_chat(self, chat_id: int) -> bool:
        if self._multi_user_enabled:
            return True
        if chat_id != self._allowed_chat_id:
            log.warning(
                "TelegramBot: ignored message from chat_id=%d (allowed=%d)",
                chat_id, self._allowed_chat_id,
            )
            return False
        return True


# ── Utilities ─────────────────────────────────────────────────────────────────

def _split_message(text: str, max_len: int = _MAX_MSG_LEN) -> list[str]:
    """Split text into chunks ≤ max_len chars, breaking on newlines when possible."""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
