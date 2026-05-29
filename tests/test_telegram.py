"""
tests/test_telegram.py — tests for core/telegram.py.

No real Telegram token needed — Bot and send methods are mocked.
Tests cover: chat_id filter, keyboard builder, message splitting, send helpers.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.telegram import TelegramBot, _split_message


# ── _split_message ────────────────────────────────────────────────────────────

def test_split_message_short():
    assert _split_message("hello") == ["hello"]


def test_split_message_exact_limit():
    text = "x" * 4096
    assert _split_message(text) == [text]


def test_split_message_long_splits():
    text = "a" * 4097
    chunks = _split_message(text)
    assert len(chunks) == 2
    assert all(len(c) <= 4096 for c in chunks)
    assert "".join(chunks) == text


def test_split_message_breaks_on_newline():
    text = "line1\n" + "x" * 4094
    chunks = _split_message(text)
    assert chunks[0] == "line1"
    assert chunks[1] == "x" * 4094


def test_split_message_three_chunks():
    text = "x" * 4096 + "y" * 4096 + "z" * 100
    chunks = _split_message(text)
    assert len(chunks) == 3
    assert all(len(c) <= 4096 for c in chunks)


# ── build_confirm_keyboard ────────────────────────────────────────────────────

def test_build_confirm_keyboard_structure():
    kb = TelegramBot.build_confirm_keyboard("generate_cv")
    assert len(kb.inline_keyboard) == 1
    row = kb.inline_keyboard[0]
    assert len(row) == 2
    assert row[0].callback_data == "generate_cv:yes"
    assert row[1].callback_data == "generate_cv:no"
    assert "✅" in row[0].text
    assert "❌" in row[1].text


def test_build_confirm_keyboard_different_actions():
    kb1 = TelegramBot.build_confirm_keyboard("send_cover")
    kb2 = TelegramBot.build_confirm_keyboard("delete_vacancy")
    assert kb1.inline_keyboard[0][0].callback_data == "send_cover:yes"
    assert kb2.inline_keyboard[0][0].callback_data == "delete_vacancy:yes"


# ── TelegramBot construction ──────────────────────────────────────────────────

def _make_bot(on_message=None, on_callback=None) -> TelegramBot:
    """Build TelegramBot with mocked Bot internals."""
    on_message = on_message or AsyncMock(return_value="ok")
    with patch("core.telegram.Bot"):
        bot = TelegramBot(
            token="fake:token",
            allowed_chat_id=12345,
            on_message=on_message,
            on_callback=on_callback,
        )
    return bot


def test_construction_does_not_raise():
    bot = _make_bot()
    assert bot._allowed_chat_id == 12345


# ── _is_allowed ───────────────────────────────────────────────────────────────

def _make_message(chat_id: int) -> MagicMock:
    msg = MagicMock()
    msg.chat.id = chat_id
    msg.text = "test"
    return msg


def test_is_allowed_correct_chat():
    bot = _make_bot()
    msg = _make_message(12345)
    assert bot._is_allowed(msg) is True


def test_is_allowed_wrong_chat():
    bot = _make_bot()
    msg = _make_message(99999)
    assert bot._is_allowed(msg) is False


# ── send_message ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_message_single_chunk():
    bot = _make_bot()
    bot._bot.send_message = AsyncMock()

    await bot.send_message("Hello!")
    bot._bot.send_message.assert_awaited_once()
    call_kwargs = bot._bot.send_message.call_args
    assert call_kwargs.args[1] == "Hello!"


@pytest.mark.asyncio
async def test_send_message_long_sends_multiple_chunks():
    bot = _make_bot()
    bot._bot.send_message = AsyncMock()

    long_text = "x" * 5000
    await bot.send_message(long_text)
    assert bot._bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_send_message_markup_on_last_chunk_only():
    bot = _make_bot()
    bot._bot.send_message = AsyncMock()
    kb = TelegramBot.build_confirm_keyboard("test")

    long_text = "x" * 5000
    await bot.send_message(long_text, reply_markup=kb)

    calls = bot._bot.send_message.call_args_list
    # First chunk: no markup
    assert calls[0].kwargs.get("reply_markup") is None
    # Last chunk: has markup
    assert calls[-1].kwargs.get("reply_markup") is kb


# ── send_document ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_document_calls_bot():
    bot = _make_bot()
    bot._bot.send_document = AsyncMock()

    with patch("core.telegram.FSInputFile") as mock_fs:
        mock_fs.return_value = MagicMock()
        await bot.send_document(Path("/tmp/cv.pdf"), caption="Your CV")

    bot._bot.send_document.assert_awaited_once()
    call_args = bot._bot.send_document.call_args
    assert call_args.args[0] == 12345
    assert call_args.kwargs.get("caption") == "Your CV"


# ── send_typing ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_typing():
    bot = _make_bot()
    bot._bot.send_chat_action = AsyncMock()

    await bot.send_typing()
    bot._bot.send_chat_action.assert_awaited_once_with(12345, "typing")
