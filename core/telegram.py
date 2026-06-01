"""
core/telegram.py — Telegram bot transport layer (aiogram 3.x, long polling).

Responsibilities:
- Start / stop long polling
- Chat ID security filter — silently drop all non-allowed senders
- Text messages → dispatch to router_callback
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
    )
    await bot.start()   # blocks until stop() called or KeyboardInterrupt
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

log = logging.getLogger(__name__)

# Max Telegram message length
_MAX_MSG_LEN = 4096

# Type alias for the router callback
OnMessageCallback = Callable[[str], Awaitable[str]]
OnCallbackCallback = Callable[[str, str], Awaitable[None]]  # action, decision


class TelegramBot:
    """Telegram bot transport layer.

    Args:
        token:          Bot API token from @BotFather.
        allowed_chat_id: Only messages from this chat_id are processed.
                         All others are silently dropped.
        on_message:     Async callback ``(text: str) -> str`` called for every
                        non-command text message. Return value is sent back to user.
        on_callback:    Async callback ``(action: str, decision: str) -> None``
                        called when inline keyboard button is pressed.
                        Optional — if None, callbacks are acked but not dispatched.
    """

    def __init__(
        self,
        token: str,
        allowed_chat_id: int,
        on_message: OnMessageCallback,
        on_callback: OnCallbackCallback | None = None,
    ) -> None:
        self._bot = Bot(token=token)
        self._dp = Dispatcher()
        self._allowed_chat_id = allowed_chat_id
        self._on_message = on_message
        self._on_callback = on_callback
        self._polling_task: asyncio.Task | None = None

        self._register_handlers()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start long polling. Blocks until stop() is called."""
        log.info("TelegramBot: starting long polling (allowed_chat_id=%d)", self._allowed_chat_id)
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
            # Only attach reply_markup to the last chunk
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

        Args:
            action: Short identifier, e.g. ``"generate_cv"`` or ``"send_cover"``.
        """
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да",  callback_data=f"{action}:yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"{action}:no"),
        ]])

    # ── Handler registration ──────────────────────────────────────────────────

    def _register_handlers(self) -> None:
        dp = self._dp

        @dp.message(Command("start"))
        async def cmd_start(message: Message) -> None:
            if not self._is_allowed(message):
                return
            await message.answer(
                "👋 <b>career-agent</b>\n\n"
                "Отправь URL вакансии — запущу CV-пайплайн.\n"
                "Или спроси что-нибудь.",
                parse_mode=ParseMode.HTML,
            )

        @dp.message(F.text)
        async def handle_text(message: Message) -> None:
            if not self._is_allowed(message):
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

        @dp.callback_query()
        async def handle_callback(query: CallbackQuery) -> None:
            if query.message and query.message.chat.id != self._allowed_chat_id:
                await query.answer()
                return
            data = query.data or ""
            log.info("TelegramBot: callback %r", data)
            await query.answer()  # remove spinner from button

            if ":" in data and self._on_callback:
                action, _, decision = data.partition(":")
                try:
                    await self._on_callback(action, decision)
                except Exception as exc:
                    log.exception("on_callback raised: %s", exc)
                    await self.send_message(f"⚠️ Ошибка обработки: {exc}")

    def _is_allowed(self, message: Message) -> bool:
        if message.chat.id != self._allowed_chat_id:
            log.warning(
                "TelegramBot: ignored message from chat_id=%d (allowed=%d)",
                message.chat.id, self._allowed_chat_id,
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
        # Try to break at last newline within max_len
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
