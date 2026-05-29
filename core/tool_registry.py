"""
core/tool_registry.py — lightweight tool registration for PydanticAI Agent.

Tools are async functions with type-annotated parameters and a docstring.
PydanticAI uses the docstring as the tool description shown to the model.

Usage:
    registry = ToolRegistry()

    @registry.register
    async def cv_fetch_jd(url: str) -> str:
        '''Fetch and parse a job description from a Djinni or DOU URL.'''
        ...

    # In Router:
    agent = Agent(model=..., tools=registry.as_pydantic_tools())
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class RegisteredTool:
    name: str
    description: str
    func: Callable[..., Any]


class ToolRegistry:
    """Registry of async tool functions for PydanticAI Agent.

    Tools are registered via decorator. The registry exposes them as a list
    of callables — PydanticAI introspects annotations + docstrings automatically.
    """

    def __init__(self) -> None:
        self._tools: list[RegisteredTool] = []

    def register(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator — add an async function to the registry.

        The function's __name__ and __doc__ are used as tool name/description.
        Returns the function unchanged (usable as plain callable too).

        Example:
            @registry.register
            async def cv_fetch_jd(url: str) -> str:
                '''Fetch and parse a job description from URL.'''
                ...
        """
        name = func.__name__
        description = (func.__doc__ or name).strip()
        self._tools.append(RegisteredTool(name=name, description=description, func=func))
        log.debug("ToolRegistry: registered %r (%s)", name, description[:60])
        return func

    def as_pydantic_tools(self) -> list[Callable[..., Any]]:
        """Return list of callables for ``Agent(tools=...)``.

        PydanticAI will wrap each function as a Tool, using its signature
        and docstring to build the tool schema sent to the model.
        """
        return [t.func for t in self._tools]

    def names(self) -> list[str]:
        """Return registered tool names (for logging / health checks)."""
        return [t.name for t in self._tools]

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={self.names()})"
