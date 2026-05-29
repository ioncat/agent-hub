"""
tests/test_llm_client.py — contract tests for core/llm_client.py.

No real API calls — Anthropic client fully mocked.
Verifies: cache_control sent, system blocks structure, error mapping, stub behaviour.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from core.llm_client import (
    ClaudeProvider,
    LLMClient,
    LLMError,
    LLMUnavailableError,
    OllamaProvider,
)

FAKE_PROFILE = "# PROFILE\nName: Test User\nSkills: Python"
FAKE_API_KEY = "sk-ant-test-0000"
FAKE_MODEL = "claude-opus-4-5"


def _make_provider(**kwargs) -> ClaudeProvider:
    defaults = dict(api_key=FAKE_API_KEY, model=FAKE_MODEL, profile_md=FAKE_PROFILE)
    return ClaudeProvider(**(defaults | kwargs))


def _fake_response(text: str) -> MagicMock:
    """Build a mock anthropic.Message with one text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


# ── Protocol check ────────────────────────────────────────────────────────────

def test_claude_provider_satisfies_protocol():
    provider = _make_provider()
    assert isinstance(provider, LLMClient)


def test_ollama_provider_satisfies_protocol():
    assert isinstance(OllamaProvider(), LLMClient)


# ── ClaudeProvider — happy path ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_sends_profile_as_cached_system_block():
    provider = _make_provider()
    fake_resp = _fake_response("Analysis result")

    with patch.object(provider._client.messages, "create", new=AsyncMock(return_value=fake_resp)) as mock_create:
        result = await provider.complete("Analyse this JD")

    assert result == "Analysis result"
    call_kwargs = mock_create.call_args.kwargs
    system = call_kwargs["system"]

    # First block: profile with cache_control
    assert system[0]["text"] == FAKE_PROFILE
    assert system[0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_complete_appends_task_system_as_second_block():
    provider = _make_provider()
    fake_resp = _fake_response("CV draft")

    with patch.object(provider._client.messages, "create", new=AsyncMock(return_value=fake_resp)) as mock_create:
        await provider.complete("Write CV", system="Phase 3 prompt here")

    system = mock_create.call_args.kwargs["system"]
    assert len(system) == 2
    assert system[1]["text"] == "Phase 3 prompt here"
    # Task system block has NO cache_control
    assert "cache_control" not in system[1]


@pytest.mark.asyncio
async def test_complete_no_system_kwarg_sends_one_block():
    provider = _make_provider()
    fake_resp = _fake_response("ok")

    with patch.object(provider._client.messages, "create", new=AsyncMock(return_value=fake_resp)) as mock_create:
        await provider.complete("Hello")

    system = mock_create.call_args.kwargs["system"]
    assert len(system) == 1


@pytest.mark.asyncio
async def test_complete_passes_model_and_max_tokens():
    provider = _make_provider(max_tokens=2048)
    fake_resp = _fake_response("ok")

    with patch.object(provider._client.messages, "create", new=AsyncMock(return_value=fake_resp)) as mock_create:
        await provider.complete("test")

    kwargs = mock_create.call_args.kwargs
    assert kwargs["model"] == FAKE_MODEL
    assert kwargs["max_tokens"] == 2048


# ── ClaudeProvider — error handling ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_status_error_raises_llm_error():
    provider = _make_provider()
    exc = anthropic.APIStatusError(
        message="bad request",
        response=MagicMock(status_code=400),
        body={},
    )

    with patch.object(provider._client.messages, "create", new=AsyncMock(side_effect=exc)):
        with pytest.raises(LLMError):
            await provider.complete("test")


@pytest.mark.asyncio
async def test_rate_limit_raises_llm_unavailable():
    provider = _make_provider()
    exc = anthropic.APIStatusError(
        message="rate limited",
        response=MagicMock(status_code=429),
        body={},
    )

    with patch.object(provider._client.messages, "create", new=AsyncMock(side_effect=exc)):
        with pytest.raises(LLMUnavailableError):
            await provider.complete("test")


@pytest.mark.asyncio
async def test_connection_error_raises_llm_unavailable():
    provider = _make_provider()
    exc = anthropic.APIConnectionError(request=MagicMock())

    with patch.object(provider._client.messages, "create", new=AsyncMock(side_effect=exc)):
        with pytest.raises(LLMUnavailableError):
            await provider.complete("test")


@pytest.mark.asyncio
async def test_empty_content_raises_llm_error():
    provider = _make_provider()
    fake_resp = MagicMock()
    fake_resp.content = []

    with patch.object(provider._client.messages, "create", new=AsyncMock(return_value=fake_resp)):
        with pytest.raises(LLMError):
            await provider.complete("test")


# ── OllamaProvider ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ollama_raises_llm_unavailable():
    with pytest.raises(LLMUnavailableError, match="stub"):
        await OllamaProvider().complete("test")


@pytest.mark.asyncio
async def test_ollama_raises_with_system():
    with pytest.raises(LLMUnavailableError):
        await OllamaProvider().complete("test", system="phase1")
