# Epic 3: LLM Client

**Status:** 🟡 In Progress
**Phase:** 1 — Core Infrastructure
**Priority:** 🔴 P0 — BLOCKER
**Blocks:** EPIC-5 (Router), EPIC-7–11 (all CV tools)

---

## Strategic Context

CV phase tools (analyze, generate, cover) need direct LLM completions with a cached PROFILE.md system block — not tool-use routing. `core/llm_client.py` is that layer.

Rule: never silently fall back from Claude to Ollama. If Claude is unavailable → raise `LLMUnavailableError`, notify user. Ollama exists only as a stub for local dev without API key.

---

## Goal

`ClaudeProvider.complete(user, system=...)` returns a text response with PROFILE.md always sent as `cache_control: ephemeral` system block. `OllamaProvider` raises `LLMUnavailableError` when called (stub).

---

## LLM Client Interface

```python
class LLMClient(Protocol):
    async def complete(self, user: str, *, system: str | None = None) -> str: ...
```

---

## User Stories

### US-301: ClaudeProvider — prompt caching

**Given** `ClaudeProvider` is initialised with `profile_md` content
**When** `complete(user, system=task_prompt)` is called
**Then** Anthropic API receives:
```python
system = [
    {"type": "text", "text": profile_md, "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": task_prompt},   # only if system kwarg passed
]
```

**Notes:**
- `profile_md` cached block is always first
- Task `system` appended as second block (no cache — changes per call)
- `max_tokens` configurable, default 4096
- On `anthropic.APIError` → raise `LLMError` with original message

---

### US-302: OllamaProvider stub

**Given** `OllamaProvider.complete()` is called
**When** anything
**Then** raises `LLMUnavailableError("Ollama is a stub — configure Claude")`

**Notes:** never silently succeed; forces explicit choice

---

### US-303: Config wiring

- `ClaudeProvider` accepts: `api_key`, `model`, `profile_md` (content string), `max_tokens`
- Caller (agent.py) loads values from `config/llm.yaml` + env var `ANTHROPIC_API_KEY`
- `profile_md` loaded from `callback-cv/skill/PROFILE.md` path in `config/profile.yaml`

---

## Implementation Plan

1. 🔴 Create `core/llm_client.py` — `LLMError`, `LLMUnavailableError`, `LLMClient` Protocol, `ClaudeProvider`, `OllamaProvider`
2. 🟡 `tests/test_llm_client.py` — mock Anthropic client, verify cache_control sent, verify OllamaProvider raises

---

## Open Questions

- [ ] PydanticAI router (EPIC-5) needs an `AnthropicModel`. Expose via `ClaudeProvider.pydantic_ai_model()` or construct directly in router?
  → Decision: router constructs `AnthropicModel` directly using same `api_key` from config. No coupling between llm_client and pydantic_ai.

---

## Acceptance Criteria

- `ClaudeProvider.complete()` sends `cache_control: ephemeral` on profile block — verified by mock
- `OllamaProvider.complete()` raises `LLMUnavailableError`
- `LLMError` raised (not raw `anthropic.APIError`) on API failure
- All tests pass without real API key
