"""
core/deps.py — shared dependency container for PydanticAI tools.

AgentDeps is passed to every tool via RunContext[AgentDeps].
Built once in agent.py at startup, reused across all router.handle() calls.

Usage in a tool:
    from pydantic_ai import RunContext
    from core.deps import AgentDeps

    async def cv_fetch_jd(ctx: RunContext[AgentDeps], url: str) -> str:
        doc = await ctx.deps.kmp_adapter.fetch_markdown(url)
        ...
"""

from dataclasses import dataclass
from pathlib import Path

from adapters.cv_adapter import CVAdapter
from adapters.kmp_adapter import KMPAdapter
from core.llm_client import ClaudeProvider


@dataclass
class AgentDeps:
    """Shared objects injected into every PydanticAI tool via RunContext.

    Attributes:
        kmp_adapter:    Async HTTP client for knowledge-mirror-parser service.
        llm:            ClaudeProvider for direct completions (CV phase tools).
        vacancies_path: Root directory for vacancy filesystem storage.
        candidate_name: Full name used in CV filenames (e.g. "Oleksii_Bondarenko").
        cv_adapter:     Subprocess wrapper for cv_to_pdf.py in callback-cv repo.
    """
    kmp_adapter: KMPAdapter
    llm: ClaudeProvider
    vacancies_path: Path
    candidate_name: str
    cv_adapter: CVAdapter
