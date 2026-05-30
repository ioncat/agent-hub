"""
core/llm_client.py — LLM abstraction layer.

ClaudeProvider: Anthropic SDK with prompt caching.
  - PROFILE.md always sent as cache_control=ephemeral system block.
  - Task system prompt appended as second block (no cache).

OllamaProvider: stub — raises LLMUnavailableError unconditionally.
  Design rule: never silently fall back from Claude to Ollama.
  If Claude unavailable → raise, notify user.

Usage:
    llm = ClaudeProvider(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model="claude-opus-4-5",
        profile_md=Path("...PROFILE.md").read_text(),
    )
    text = await llm.complete(user="Analyse this JD:", system=phase1_prompt)
"""

import asyncio
import logging
import sys
from typing import Protocol, runtime_checkable

import anthropic

log = logging.getLogger(__name__)

# ── Token pricing (USD per 1M tokens) ────────────────────────────────────────
# Source: https://anthropic.com/pricing (verified 2026-05-30)
# Opus 4.x: $5/$25, Sonnet 4.x: $3/$15, Haiku 4.5: $1/$5
_PRICING: dict[str, dict[str, float]] = {
    # Opus 4 family — $5/$25 input/output
    "claude-opus-4-5":   {"input": 5.0,  "output": 25.0, "cache_write": 6.25, "cache_read": 0.50},
    "claude-opus-4":     {"input": 5.0,  "output": 25.0, "cache_write": 6.25, "cache_read": 0.50},
    # Sonnet 4 family — $3/$15 input/output
    "claude-sonnet-4-5": {"input": 3.0,  "output": 15.0, "cache_write": 3.75, "cache_read": 0.30},
    "claude-sonnet-4":   {"input": 3.0,  "output": 15.0, "cache_write": 3.75, "cache_read": 0.30},
    # Haiku 4.5 — $1/$5 input/output
    "claude-haiku-4-5":  {"input": 1.0,  "output": 5.0,  "cache_write": 1.25, "cache_read": 0.10},
    "claude-haiku-3-5":  {"input": 0.8,  "output": 4.0,  "cache_write": 1.00, "cache_read": 0.08},
}
_PRICING_FALLBACK = {"input": 5.0, "output": 25.0, "cache_write": 6.25, "cache_read": 0.50}


def _normalize_model(model: str) -> str:
    """Strip date suffix from model name for pricing lookup.

    e.g. 'claude-opus-4-5-20251101' → 'claude-opus-4-5'
    """
    import re
    return re.sub(r"-\d{8}$", "", model)


def _calc_cost(model: str, inp: int, out: int, cw: int, cr: int) -> float:
    """Calculate USD cost for a single API call."""
    p = _PRICING.get(_normalize_model(model), _PRICING_FALLBACK)
    return (
        inp * p["input"]
        + out * p["output"]
        + cw * p["cache_write"]
        + cr * p["cache_read"]
    ) / 1_000_000


# ── Exceptions ────────────────────────────────────────────────────────────────


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMUnavailableError(LLMError):
    """Claude is unavailable or Ollama stub is called."""


# ── Protocol ─────────────────────────────────────────────────────────────────


@runtime_checkable
class LLMClient(Protocol):
    """Minimal interface for an LLM completion provider.

    Implementations: ClaudeProvider, OllamaProvider (stub).
    Injected into router and CV tools — not instantiated directly there.
    """

    async def complete(self, user: str, *, system: str | None = None) -> str:
        """Return LLM text completion.

        Args:
            user:   User-turn message (JD text, task input, etc.).
            system: Optional task-level system prompt appended after PROFILE.md.
                    Changes per call — not cached.

        Returns:
            Plain text response from the model.

        Raises:
            LLMError: API error, network failure, or response parsing failure.
            LLMUnavailableError: Provider is unavailable (stub or quota exceeded).
        """
        ...


# ── ClaudeProvider ────────────────────────────────────────────────────────────


class ClaudeProvider:
    """Anthropic Claude completion provider with prompt caching.

    PROFILE.md is always the first system block and is marked
    cache_control=ephemeral so Anthropic caches it across calls.

    Args:
        api_key:    Anthropic API key (from ANTHROPIC_API_KEY env var).
        model:      Model identifier, e.g. "claude-opus-4-5".
        profile_md: Full text content of PROFILE.md. Sent as cached system block.
        max_tokens: Max tokens for each completion. Default 4096.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        profile_md: str,
        max_tokens: int = 4096,
        testing_mode: bool = False,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._profile_md = profile_md
        self._max_tokens = max_tokens
        self._testing_mode = testing_mode
        # ── Session token counters (reset on each ClaudeProvider instance) ───
        self._sess_calls = 0
        self._sess_input = 0
        self._sess_output = 0
        self._sess_cache_write = 0
        self._sess_cache_read = 0
        self._sess_cost_usd = 0.0
        self._last_call_usage: dict | None = None

    async def _confirm_call(self, user: str, system: str | None) -> bool:
        """In testing mode: print warning and ask for confirmation.

        Returns True if call should proceed, False to skip.
        Runs input() in executor so it doesn't block the event loop.
        """
        if not self._testing_mode:
            return True

        preview = user[:200].replace("\n", " ")
        sys_preview = (system or "")[:100].replace("\n", " ")
        print(
            f"\n⚠️  [TESTING MODE] About to call Claude API ({self._model})\n"
            f"   system: {sys_preview!r}…\n"
            f"   user:   {preview!r}…\n"
            f"   user_len={len(user)} chars",
            flush=True,
        )
        answer = await asyncio.get_event_loop().run_in_executor(
            None, lambda: input("   Proceed? [y/N]: ").strip().lower()
        )
        if answer != "y":
            log.info("ClaudeProvider: call skipped by user in testing mode")
            return False
        return True

    async def complete(self, user: str, *, system: str | None = None) -> str:
        """Call Claude with PROFILE.md cached + optional task system prompt."""
        if not await self._confirm_call(user, system):
            raise LLMError("LLM call cancelled by user (testing mode)")

        system_parts: list[dict] = [
            {
                "type": "text",
                "text": self._profile_md,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if system:
            system_parts.append({"type": "text", "text": system})

        log.debug(
            "ClaudeProvider.complete model=%s system_blocks=%d user_len=%d",
            self._model, len(system_parts), len(user),
        )

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_parts,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIStatusError as exc:
            log.error("Claude API error %d: %s", exc.status_code, exc.message)
            if exc.status_code in (429, 529):
                raise LLMUnavailableError(
                    f"Claude quota/overload (HTTP {exc.status_code}): {exc.message}"
                ) from exc
            raise LLMError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            log.error("Claude connection error: %s", exc)
            raise LLMUnavailableError(f"Claude unreachable: {exc}") from exc

        # ── Token accounting ──────────────────────────────────────────────────
        u = response.usage
        inp = u.input_tokens
        out = u.output_tokens

        # cache_creation: SDK ≥0.40 returns CacheCreation object with per-TTL fields;
        # older SDK returns flat cache_creation_input_tokens int.
        cc = getattr(u, "cache_creation", None)
        if cc is not None:
            cw = (getattr(cc, "ephemeral_5m_input_tokens", 0) or 0) + \
                 (getattr(cc, "ephemeral_1h_input_tokens", 0) or 0)
        else:
            cw = getattr(u, "cache_creation_input_tokens", 0) or 0
        cr = getattr(u, "cache_read_input_tokens", 0) or 0

        actual_model = str(getattr(response, "model", None) or self._model)
        cost = _calc_cost(actual_model, inp, out, cw, cr)

        self._sess_calls += 1
        self._sess_input += inp
        self._sess_output += out
        self._sess_cache_write += cw
        self._sess_cache_read += cr
        self._sess_cost_usd += cost
        self._last_call_usage = {
            "model": self._model,
            "input_tokens": inp,
            "output_tokens": out,
            "cache_write_tokens": cw,
            "cache_read_tokens": cr,
            "cost_usd": round(cost, 6),
        }

        log.info(
            "LLM call #%d [%s]: in=%d out=%d cache_write=%d cache_read=%d cost=$%.4f"
            " | session total: calls=%d cost=$%.4f",
            self._sess_calls, actual_model, inp, out, cw, cr, cost,
            self._sess_calls, self._sess_cost_usd,
        )

        # Extract text from first content block
        if not response.content or response.content[0].type != "text":
            raise LLMError("Claude returned no text content")

        text = response.content[0].text
        log.debug("ClaudeProvider.complete → %d chars", len(text))
        return text

    @property
    def model(self) -> str:
        return self._model

    @property
    def raw_client(self) -> anthropic.AsyncAnthropic:
        """Expose underlying client for PydanticAI router (EPIC-5)."""
        return self._client

    @property
    def session_summary(self) -> dict:
        """Cumulative token usage and cost since this provider was created."""
        return {
            "calls": self._sess_calls,
            "input_tokens": self._sess_input,
            "output_tokens": self._sess_output,
            "cache_write_tokens": self._sess_cache_write,
            "cache_read_tokens": self._sess_cache_read,
            "cost_usd": round(self._sess_cost_usd, 6),
        }

    @property
    def last_call_usage(self) -> dict | None:
        """Usage dict from the most recent complete() call. None if no calls yet."""
        return self._last_call_usage

    def log_session_summary(self) -> None:
        """Log cumulative session cost — call at agent shutdown."""
        s = self.session_summary
        log.info(
            "LLM session summary: calls=%d in=%d out=%d"
            " cache_write=%d cache_read=%d total_cost=$%.4f",
            s["calls"], s["input_tokens"], s["output_tokens"],
            s["cache_write_tokens"], s["cache_read_tokens"], s["cost_usd"],
        )


# ── OllamaProvider (stub) ─────────────────────────────────────────────────────


class OllamaProvider:
    """Stub LLM provider. Raises LLMUnavailableError on every call.

    Exists as a placeholder for local dev without an Anthropic API key.
    Rule: never silently succeed — the caller must handle the error and
    notify the user that Claude is required.
    """

    async def complete(self, user: str, *, system: str | None = None) -> str:
        raise LLMUnavailableError(
            "OllamaProvider is a stub — configure ANTHROPIC_API_KEY and use ClaudeProvider."
        )
