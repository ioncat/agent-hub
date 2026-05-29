"""
core/router.py — PydanticAI Agent that routes user messages to registered tools.

The Router is the brain of the agent:
- Receives raw user text from Telegram
- PydanticAI Agent decides which tool to call (or responds directly)
- Returns plain text reply to TelegramBot

DI pattern: Router constructed in agent.py, injected into TelegramBot.on_message.

Usage:
    router = Router(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        registry=registry,
    )
    reply = await router.handle("https://djinni.co/jobs/123/")
"""

import logging

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from core.deps import AgentDeps
from core.tool_registry import ToolRegistry

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Ты личный AI-агент для управления процессом поиска работы.
Помогаешь пользователю: анализируешь вакансии, генерируешь CV и сопроводительные письма, отслеживаешь статус заявок.

Правила:
- Если пользователь присылает URL (djinni.co, jobs.dou.ua, linkedin.com) → вызови инструмент cv_fetch_jd
- Если просит показать статус / трекер → вызови cv_get_tracker
- Если просит создать/сгенерировать CV → запусти cv_analyze, затем cv_generate
- Для общих вопросов — отвечай напрямую, без инструментов
- Отвечай на языке пользователя (русский или украинский)
- Будь кратким и по делу
"""


class Router:
    """PydanticAI Agent wrapper for intent-to-tool routing.

    Args:
        api_key:  Anthropic API key. Used to build AnthropicProvider.
        model:    Model identifier, e.g. "claude-opus-4-5".
        registry: ToolRegistry with all registered domain tools.
        deps:     AgentDeps injected into tools via RunContext on every run.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        registry: ToolRegistry,
        deps: AgentDeps,
    ) -> None:
        provider = AnthropicProvider(api_key=api_key)
        anthropic_model = AnthropicModel(model, provider=provider)

        self._agent: Agent[AgentDeps, str] = Agent(
            model=anthropic_model,
            deps_type=AgentDeps,
            system_prompt=_SYSTEM_PROMPT,
            tools=registry.as_pydantic_tools(),
            output_type=str,
        )
        self._deps = deps
        self._registry = registry
        log.info(
            "Router: ready — model=%s tools=%s",
            model, registry.names(),
        )

    async def handle(self, text: str) -> str:
        """Route a user text message through the PydanticAI Agent.

        Args:
            text: Raw message text from Telegram.

        Returns:
            Plain text reply to send back to the user.

        Raises:
            Exception: Propagated to TelegramBot handler which formats it as ⚠️ error.
        """
        log.info("Router.handle: %r", text[:100])
        result = await self._agent.run(text, deps=self._deps)
        reply = str(result.output)
        log.info("Router.handle → %d chars", len(reply))
        return reply
