# Epic 5: Core Agent Routing

**Status:** 🟡 In Progress
**Phase:** 1 — Core Infrastructure
**Priority:** 🔴 P0 — BLOCKER (last Phase 1 blocker)
**Blocks:** Nothing further — Phase 1 complete after this

---

## Strategic Context

Phase 1 ends here. After EPIC-5, the bot boots, accepts messages, routes them via
PydanticAI Agent, and responds. CV tools (EPIC-7+) register into the ToolRegistry —
no changes to core needed.

---

## Goal

Three files:
- `core/settings.py` — load config from env vars + .env file
- `core/tool_registry.py` — register async functions as PydanticAI tools
- `core/router.py` — PydanticAI Agent with system prompt, dispatches text → tool → reply
- `agent.py` — entry point: init DB, build LLM + registry + router + bot, start polling

---

## User Stories

### US-501: Settings from env

`Settings` dataclass loaded from env vars (python-dotenv). Fails fast on missing required vars.

Required: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
Optional with defaults: `LLM_MODEL`, `PROFILE_MD_PATH`, `DB_PATH`, `KMP_BASE_URL`

---

### US-502: Tool registry

```python
registry = ToolRegistry()

@registry.register
async def cv_fetch_jd(url: str) -> str:
    """Fetch and parse a job description from URL."""
    ...

registry.as_pydantic_tools()  # → list[Callable] for Agent(tools=...)
```

Registry is list-based. Tools added in tool files (EPIC-7+), not in core.

---

### US-503: Router — PydanticAI Agent

`Router(api_key, model, registry)` builds a PydanticAI `Agent` with:
- `AnthropicModel` via `AnthropicProvider(api_key=...)`
- System prompt describing agent role
- Registered tools from registry

`await router.handle(text) → str` — runs agent, returns output as string.

---

### US-504: agent.py entry point

Startup sequence:
1. Load `Settings`
2. `database.configure()` + `await init_db()`
3. Build `ClaudeProvider` (loads PROFILE.md)
4. Build `ToolRegistry` + register tools
5. Build `Router`
6. Build `TelegramBot(on_message=router.handle)`
7. `await bot.start()` — blocks

Graceful shutdown on `KeyboardInterrupt` or `SIGTERM`.

---

## Implementation Plan

1. 🔴 `core/settings.py` — `Settings` dataclass, `load_settings()`, fast-fail on missing vars
2. 🔴 `core/tool_registry.py` — `ToolRegistry` with `register` decorator and `as_pydantic_tools()`
3. 🔴 `core/router.py` — `Router` wrapping PydanticAI `Agent`
4. 🟠 `agent.py` — full startup sequence
5. 🟠 `.env.example` — all required + optional vars documented
6. 🟡 `tests/test_router.py` — ToolRegistry tests; Router.handle mocked

---

## Acceptance Criteria

- `python agent.py` starts without error (with valid .env)
- Text message flows: Telegram → Router → PydanticAI Agent → reply → Telegram
- New tool registered via `@registry.register` without modifying core
- Missing required env var → clear error on startup (not buried exception)
