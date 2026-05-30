"""
tools/cv_analyze.py — CV pipeline Phase 1+2 analysis.

Pipeline step 1: JD.md → Phase 1 (JD analysis) → Phase 2 (fit assessment) → JD_analysis.md.

Flow:
    1. Load vacancy from DB by ID.
    2. Read JD.md from disk.
    3. Phase 1: LLM call with phase1_analysis.md prompt → structural JD analysis.
    4. Phase 2: LLM call with phase2_fit.md prompt + Phase 1 output → fit + Quick Scan.
    5. Extract Quick Scan block from Phase 2 output.
    6. Write JD_analysis.md to vacancy folder (Quick Scan at top).
    7. Update vacancy status to "analyzed".
    8. Return Quick Scan block for Telegram.

Tool registered in agent.py via ToolRegistry.
Receives shared dependencies via RunContext[AgentDeps].
"""

import logging
import re
import time
from datetime import datetime
from pathlib import Path

from pydantic_ai import RunContext

from core.deps import AgentDeps
from core.llm_client import LLMError
from db import database

log = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


async def cv_analyze(ctx: RunContext[AgentDeps], vacancy_id: int) -> str:
    """Run Phase 1+2 analysis on a fetched vacancy and save JD_analysis.md.

    Reads JD.md from the vacancy folder, calls Claude with the phase 1 analysis
    prompt, then calls Claude again with the phase 2 fit assessment prompt.
    Saves the full analysis to JD_analysis.md and returns the Quick Scan block.

    Args:
        vacancy_id: DB id of the vacancy (returned by cv_fetch_jd).

    Returns:
        Quick Scan block as Telegram-formatted text, prefixed with ✅ confirmation.
    """
    log.info("cv_analyze: vacancy_id=%d", vacancy_id)

    # ── Load vacancy from DB ──────────────────────────────────────────────────
    vacancy = await database.get_vacancy_by_id(vacancy_id)
    if not vacancy:
        return (
            f"⚠️ Вакансия #{vacancy_id} не найдена в базе.\n"
            f"Сначала сохрани URL командой fetch."
        )

    title = vacancy["title"] or "Без названия"
    markdown_path = vacancy["markdown_path"]

    # ── Read JD.md ────────────────────────────────────────────────────────────
    jd_path = Path(markdown_path)
    if not jd_path.exists():
        log.error("cv_analyze: JD.md not found at %s", jd_path)
        return f"⚠️ Файл JD.md не найден:\n<code>{jd_path}</code>"

    jd_text = jd_path.read_text(encoding="utf-8")

    # ── Load prompts from disk ────────────────────────────────────────────────
    phase1_prompt = (_PROMPTS_DIR / "phase1_analysis.md").read_text(encoding="utf-8")
    phase2_prompt = (_PROMPTS_DIR / "phase2_fit.md").read_text(encoding="utf-8")

    # ── Phase 1: JD Analysis ──────────────────────────────────────────────────
    run1_id = await database.insert_pipeline_run(vacancy_id, phase="phase1")
    await database.update_pipeline_run(run1_id, status="running")

    try:
        log.info("cv_analyze: Phase 1 start — vacancy_id=%d", vacancy_id)
        t0 = time.monotonic()
        phase1_output = await ctx.deps.llm.complete(jd_text, system=phase1_prompt)
        log.info("cv_analyze: Phase 1 done — %d chars, elapsed=%.1fs", len(phase1_output), time.monotonic() - t0)
        if u := ctx.deps.llm.last_call_usage:
            await database.insert_llm_usage(phase="phase1", vacancy_id=vacancy_id, **u)
    except LLMError as exc:
        await database.update_pipeline_run(run1_id, status="error", error_message=str(exc))
        log.error("cv_analyze: Phase 1 LLM error: %s", exc)
        return f"⚠️ Ошибка Claude на фазе 1:\n{exc}"

    await database.update_pipeline_run(run1_id, status="done")

    # ── Phase 2: Candidate Fit Assessment ─────────────────────────────────────
    run2_id = await database.insert_pipeline_run(vacancy_id, phase="phase2")
    await database.update_pipeline_run(run2_id, status="running")

    phase2_user = (
        f"{jd_text}\n\n"
        f"---\n\n"
        f"Phase 1 Analysis:\n\n{phase1_output}"
    )

    try:
        log.info("cv_analyze: Phase 2 start — vacancy_id=%d", vacancy_id)
        t0 = time.monotonic()
        phase2_output = await ctx.deps.llm.complete(phase2_user, system=phase2_prompt)
        log.info("cv_analyze: Phase 2 done — %d chars, elapsed=%.1fs", len(phase2_output), time.monotonic() - t0)
        if u := ctx.deps.llm.last_call_usage:
            await database.insert_llm_usage(phase="phase2", vacancy_id=vacancy_id, **u)
    except LLMError as exc:
        await database.update_pipeline_run(run2_id, status="error", error_message=str(exc))
        log.error("cv_analyze: Phase 2 LLM error: %s", exc)
        return f"⚠️ Ошибка Claude на фазе 2:\n{exc}"

    # ── Extract Quick Scan ────────────────────────────────────────────────────
    quick_scan = _extract_quick_scan(phase2_output)

    # ── Write JD_analysis.md ──────────────────────────────────────────────────
    analysis_path = jd_path.parent / "JD_analysis.md"
    analysis_content = _build_analysis_file(
        title=title,
        url=vacancy["url"],
        phase1=phase1_output,
        phase2=phase2_output,
        quick_scan=quick_scan,
    )
    analysis_path.write_text(analysis_content, encoding="utf-8")
    log.info("cv_analyze: saved JD_analysis.md → %s", analysis_path)

    await database.update_pipeline_run(
        run2_id, status="done", result_path=str(analysis_path)
    )

    # ── Update vacancy status ─────────────────────────────────────────────────
    await database.update_vacancy_status(vacancy_id, "analyzed")

    return (
        f"✅ Анализ готов — <b>{title}</b>\n"
        f"Файл: <code>{analysis_path}</code>\n\n"
        f"{quick_scan}"
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_quick_scan(phase2_output: str) -> str:
    """Extract the ## Quick Scan block from Phase 2 LLM output.

    Matches from '## Quick Scan' to the next '## ' section or end of string.
    Falls back to first 500 chars if the block is not found.
    """
    match = re.search(
        r"(##\s*Quick Scan\b.*?)(?=\n##\s|\Z)",
        phase2_output,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    log.warning("cv_analyze: Quick Scan block not found in Phase 2 output; using fallback")
    return phase2_output[:500].strip()


def _build_analysis_file(
    title: str,
    url: str,
    phase1: str,
    phase2: str,
    quick_scan: str,
) -> str:
    """Compose JD_analysis.md content.

    Quick Scan goes at the top (as required by phase2_fit.md prompt).
    Full Phase 2 assessment and Phase 1 JD analysis follow.
    """
    date = datetime.now().strftime("%Y-%m-%d")
    return (
        f"# Analysis: {title}\n\n"
        f"Source: {url}\n"
        f"Date: {date}\n\n"
        f"---\n\n"
        f"{quick_scan}\n\n"
        f"---\n\n"
        f"## Phase 2: Candidate Fit Assessment\n\n"
        f"{phase2}\n\n"
        f"---\n\n"
        f"## Phase 1: JD Analysis\n\n"
        f"{phase1}\n"
    )
