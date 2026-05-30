"""
tools/cv_cover.py — CV pipeline Phase 4: cover message.

Pipeline step 3 (final):
    Phase 4 — cover message tailored to vacancy + approved CV.
    Output  — [Name]_Cover.md saved to vacancy folder; message text returned for Telegram.

Phase 4 inputs:
    1. JD text          (JD.md)
    2. JD analysis      (JD_analysis.md — Phase 1+2+3.5 combined)
    3. Approved CV text ([Name]_CV.md — Phase 3.5 final CV)

Cover language auto-detected by LLM: Ukrainian JD → Ukrainian cover, English JD → English cover.

Tool registered in agent.py via ToolRegistry.
Receives shared dependencies via RunContext[AgentDeps].
"""

import logging
import re
import time
from pathlib import Path

from pydantic_ai import RunContext

from core.deps import AgentDeps
from core.llm_client import LLMError
from db import database

log = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


async def cv_cover(ctx: RunContext[AgentDeps], vacancy_id: int) -> str:
    """Generate a tailored cover message for a vacancy that has an approved CV.

    Reads JD.md + JD_analysis.md + [Name]_CV.md, calls Claude with the
    phase4_cover.md prompt, saves [Name]_Cover.md, and returns the cover
    message text ready to copy-paste into a job application.

    Args:
        vacancy_id: DB id of the vacancy (must have status 'cv_generated').

    Returns:
        Cover message text prefixed with ✅ confirmation and file path.
    """
    log.info("cv_cover: vacancy_id=%d", vacancy_id)

    # ── Load vacancy from DB ──────────────────────────────────────────────────
    vacancy = await database.get_vacancy_by_id(vacancy_id)
    if not vacancy:
        return (
            f"⚠️ Вакансия #{vacancy_id} не найдена в базе.\n"
            f"Сначала сохрани URL (fetch), запусти анализ (analyze) и сгенерируй CV (generate)."
        )

    title = vacancy["title"] or "Без названия"
    markdown_path = vacancy["markdown_path"]

    # ── Read source files ─────────────────────────────────────────────────────
    jd_path = Path(markdown_path)
    if not jd_path.exists():
        return f"⚠️ Файл JD.md не найден:\n<code>{jd_path}</code>"

    analysis_path = jd_path.parent / "JD_analysis.md"
    if not analysis_path.exists():
        return (
            f"⚠️ JD_analysis.md не найден. "
            f"Сначала запусти анализ для вакансии #{vacancy_id}."
        )

    safe_name = re.sub(r"[^\w\-]", "_", ctx.deps.candidate_name)
    cv_path = jd_path.parent / f"{safe_name}_CV.md"
    if not cv_path.exists():
        return (
            f"⚠️ {safe_name}_CV.md не найден. "
            f"Сначала сгенерируй CV для вакансии #{vacancy_id}."
        )

    jd_text = jd_path.read_text(encoding="utf-8")
    analysis_text = analysis_path.read_text(encoding="utf-8")
    cv_text = cv_path.read_text(encoding="utf-8")

    # ── Load prompt ───────────────────────────────────────────────────────────
    phase4_prompt = (_PROMPTS_DIR / "phase4_cover.md").read_text(encoding="utf-8")

    # ── Phase 4: Cover Message ────────────────────────────────────────────────
    run_id = await database.insert_pipeline_run(vacancy_id, phase="phase4")
    await database.update_pipeline_run(run_id, status="running")

    phase4_user = (
        f"JD Text:\n\n{jd_text}\n\n"
        f"---\n\n"
        f"JD Analysis:\n\n{analysis_text}\n\n"
        f"---\n\n"
        f"Approved CV:\n\n{cv_text}"
    )

    try:
        log.info("cv_cover: Phase 4 start — vacancy_id=%d", vacancy_id)
        t0 = time.monotonic()
        cover_text = await ctx.deps.llm.complete(phase4_user, system=phase4_prompt)
        log.info("cv_cover: Phase 4 done — %d chars, elapsed=%.1fs", len(cover_text), time.monotonic() - t0)
        if u := ctx.deps.llm.last_call_usage:
            await database.insert_llm_usage(phase="phase4", vacancy_id=vacancy_id, **u)
    except LLMError as exc:
        await database.update_pipeline_run(run_id, status="error", error_message=str(exc))
        log.error("cv_cover: Phase 4 LLM error: %s", exc)
        return f"⚠️ Ошибка Claude на фазе 4:\n{exc}"

    # ── Save [Name]_Cover.md ──────────────────────────────────────────────────
    cover_md_path = jd_path.parent / f"{safe_name}_Cover.md"
    cover_md_path.write_text(cover_text, encoding="utf-8")
    log.info("cv_cover: saved Cover.md → %s", cover_md_path)

    await database.update_pipeline_run(
        run_id, status="done", result_path=str(cover_md_path)
    )

    # ── Update vacancy status ─────────────────────────────────────────────────
    await database.update_vacancy_status(vacancy_id, "cover_generated")

    # ── Build Telegram reply ──────────────────────────────────────────────────
    return (
        f"✅ Cover message готов — <b>{title}</b>\n\n"
        f"{cover_text}\n\n"
        f"---\n\n"
        f"Файл: <code>{cover_md_path}</code>"
    )
