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
