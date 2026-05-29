# Epic 4: Telegram Bot

**Status:** 🟡 In Progress
**Phase:** 1 — Core Infrastructure
**Priority:** 🔴 P0 — BLOCKER
**Blocks:** EPIC-5 (Router wiring), all user-facing output

---

## Strategic Context

Telegram is the primary UI. All user input arrives as Telegram messages;
all output (CV, cover letter, tracker summary) is sent back via bot.
This epic establishes the transport layer — not business logic.

Personal bot: one allowed `chat_id` (from config). Any other sender is silently ignored.

---

## Goal

`TelegramBot` class handles:
- Long polling startup / graceful shutdown
- Chat ID security filter (all unknown senders dropped)
- Text message → router callback dispatch
- Send helpers: `send_message()`, `send_document()`
- Inline keyboard builder + callback dispatch

---

## User Stories

### US-401: Start and stop long polling

**Given** `TelegramBot` is constructed with a valid token
**When** `await bot.start()` is called
**Then** aiogram Dispatcher starts long polling; `await bot.stop()` shuts it down cleanly

---

### US-402: Chat ID security filter

**Given** a message arrives from an unknown `chat_id`
**When** any handler runs
**Then** message is silently dropped (no response, no error)

---

### US-403: Text message → router dispatch

**Given** a text message arrives from the allowed `chat_id`
**When** handler fires
**Then** `router_callback(text: str) → str` is awaited and the result is sent back

---

### US-404: Send helpers

- `send_message(text, reply_markup=None)` — plain text or with inline keyboard
- `send_document(file_path, caption=None)` — sends file (CV PDF, etc.)
- `send_typing()` — sends "typing…" action while processing

---

### US-405: Inline keyboard helpers

`build_confirm_keyboard(action: str)` → `InlineKeyboardMarkup` with two buttons:
- `✅ Да` → callback_data `{action}:yes`
- `❌ Нет` → callback_data `{action}:no`

Callback handler parses `action:decision` and calls `callback_registry[action](decision)`.

---

## Implementation Plan

1. 🔴 Create `core/telegram.py` — `TelegramBot` class, `/start` handler, text handler, callback handler, send helpers
2. 🟡 `tests/test_telegram.py` — test chat_id filter, keyboard builder, send helpers (mock Bot)

---

## Open Questions

- [ ] Markdown parse mode? (MarkdownV2 vs HTML — HTML easier to escape)
- [ ] Max message length guard? (Telegram limit 4096 chars — split long messages)

---

## Acceptance Criteria

- Messages from wrong `chat_id` → no response
- Text message → router callback → reply sent
- `send_document()` delivers file
- Inline keyboard `✅/❌` renders correctly and callbacks are dispatched
