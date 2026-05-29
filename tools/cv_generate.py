"""
tools/cv_generate.py — CV pipeline Phase 3 + 3.5: draft → self-review → final CV + PDF.

Pipeline step 2:
    Phase 3  — hidden CV draft (not shown to user).
    Phase 3.5 — self-review; produces a self-critique block + the revised CV.
    Output   — [Name]_CV.md + [Name]_CV.pdf saved to vacancy folder.

Phase 3.5 output structure:
    CV SELF-REVIEW        ← review block (shown to user + appended to JD_analysis.md)
    ——————————————
    ❌ Remove / doesn't fit:
    ⚠️ Weaken / compress:
    🔧 Strengthen / reframe:
    ✅ Strong — keep as is:

    [Name]                ← final CV starts here (name/headline/contacts)
    [Headline]
    [Contacts]

    SUMMARY               ← anchor used to split review from CV
    ...

Tool registered in agent.py via ToolRegistry.
Receives shared dependencies via RunContext[AgentDeps].
"""

import logging
import re
import time
from pathlib import Path

from pydantic_ai import RunContext

from adapters.cv_adapter import CVAdapterError
from core.deps import AgentDeps
from core.llm_client import LLMError
from db import database

log = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


async def cv_generate(
    ctx: RunContext[AgentDeps],
    vacancy_id: int,
    language: str = "English",
) -> str:
    """Generate a tailored CV for a fetched and analysed vacancy.

    Runs Phase 3 (hidden draft) then Phase 3.5 (self-review). Saves the final
    reviewed CV as [Name]_CV.md and generates a PDF. Returns the self-review
    block so the user can see what was changed and why.

    Args:
        vacancy_id: DB id of the vacancy (must be status 'analyzed').
        language:   Target CV language — 'English', 'Ukrainian', or 'both'.

    Returns:
        Self-review critique block + file paths confirmation.
    """
    log.info("cv_generate: vacancy_id=%d language=%s", vacancy_id, language)

    # ── Load vacancy from DB ──────────────────────────────────────────────────
    vacancy = await database.get_vacancy_by_id(vacancy_id)
    if not vacancy:
        return (
            f"⚠️ Вакансия #{vacancy_id} не найдена в базе.\n"
            f"Сначала сохрани URL (fetch) и запусти анализ (analyze)."
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
            f"⚠️ JD_analysis.md не найден. Сначала запусти анализ для вакансии #{vacancy_id}."
        )

    jd_text = jd_path.read_text(encoding="utf-8")
    analysis_text = analysis_path.read_text(encoding="utf-8")

    # ── Load prompts ──────────────────────────────────────────────────────────
    phase3_prompt = (_PROMPTS_DIR / "phase3_cv_draft.md").read_text(encoding="utf-8")
    phase35_prompt = (_PROMPTS_DIR / "phase3_5_review.md").read_text(encoding="utf-8")

    # ── Phase 3: CV Draft (hidden) ────────────────────────────────────────────
    run3_id = await database.insert_pipeline_run(vacancy_id, phase="phase3")
    await database.update_pipeline_run(run3_id, status="running")

    phase3_user = (
        f"JD Text:\n\n{jd_text}\n\n"
        f"---\n\n"
        f"JD Analysis:\n\n{analysis_text}\n\n"
        f"---\n\n"
        f"Target language: {language}\n"
        f"Candidate name: {ctx.deps.candidate_name}"
    )

    try:
        log.info("cv_generate: Phase 3 start — vacancy_id=%d", vacancy_id)
        t0 = time.monotonic()
        phase3_draft = await ctx.deps.llm.complete(phase3_user, system=phase3_prompt)
        log.info("cv_generate: Phase 3 done — %d chars, elapsed=%.1fs", len(phase3_draft), time.monotonic() - t0)
    except LLMError as exc:
        await database.update_pipeline_run(run3_id, status="error", error_message=str(exc))
        log.error("cv_generate: Phase 3 LLM error: %s", exc)
        return f"⚠️ Ошибка Claude на фазе 3:\n{exc}"

    await database.update_pipeline_run(run3_id, status="done")

    # Save raw draft for debugging (not shown to user)
    draft_path = jd_path.parent / "CV_draft_p3.md"
    draft_path.write_text(phase3_draft, encoding="utf-8")

    # ── Phase 3.5: Self-Review ────────────────────────────────────────────────
    run35_id = await database.insert_pipeline_run(vacancy_id, phase="phase3_5")
    await database.update_pipeline_run(run35_id, status="running")

    phase35_user = (
        f"JD Text:\n\n{jd_text}\n\n"
        f"---\n\n"
        f"JD Analysis:\n\n{analysis_text}\n\n"
        f"---\n\n"
        f"CV Draft:\n\n{phase3_draft}"
    )

    try:
        log.info("cv_generate: Phase 3.5 start — vacancy_id=%d", vacancy_id)
        t0 = time.monotonic()
        phase35_output = await ctx.deps.llm.complete(phase35_user, system=phase35_prompt)
        log.info("cv_generate: Phase 3.5 done — %d chars, elapsed=%.1fs", len(phase35_output), time.monotonic() - t0)
    except LLMError as exc:
        await database.update_pipeline_run(run35_id, status="error", error_message=str(exc))
        log.error("cv_generate: Phase 3.5 LLM error: %s", exc)
        return f"⚠️ Ошибка Claude на фазе 3.5:\n{exc}"

    # ── Split review block from final CV ──────────────────────────────────────
    review_block, final_cv = _split_review_and_cv(phase35_output)

    if not final_cv:
        log.warning("cv_generate: could not extract CV from Phase 3.5 output — using full output")
        final_cv = phase35_output

    # ── Save [Name]_CV.md ─────────────────────────────────────────────────────
    safe_name = re.sub(r"[^\w\-]", "_", ctx.deps.candidate_name)
    cv_md_path = jd_path.parent / f"{safe_name}_CV.md"
    cv_md_path.write_text(final_cv, encoding="utf-8")
    log.info("cv_generate: saved CV.md → %s", cv_md_path)

    await database.update_pipeline_run(
        run35_id, status="done", result_path=str(cv_md_path)
    )

    # ── Append review to JD_analysis.md ──────────────────────────────────────
    if review_block:
        with analysis_path.open("a", encoding="utf-8") as f:
            f.write(f"\n\n---\n\n## Phase 3.5: CV Self-Review\n\n{review_block}\n")

    # ── Update vacancy status ─────────────────────────────────────────────────
    await database.update_vacancy_status(vacancy_id, "cv_generated")

    # ── Generate PDF (best-effort) ────────────────────────────────────────────
    pdf_msg = ""
    try:
        pdf_path = await ctx.deps.cv_adapter.generate_pdf(cv_md_path)
        pdf_msg = f"PDF: <code>{pdf_path}</code>\n"
    except (CVAdapterError, FileNotFoundError, Exception) as exc:
        log.warning("cv_generate: PDF generation failed: %s", exc)
        pdf_msg = "PDF: не удалось сгенерировать (проверь логи)\n"

    # ── Build Telegram reply ──────────────────────────────────────────────────
    return (
        f"✅ CV готов — <b>{title}</b>\n\n"
        f"{review_block or '(self-review block not extracted)'}\n\n"
        f"---\n\n"
        f"MD: <code>{cv_md_path}</code>\n"
        f"{pdf_msg}"
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_review_and_cv(phase35_output: str) -> tuple[str, str]:
    """Split Phase 3.5 output into (review_block, final_cv).

    The CV starts with Name / Headline / Contacts block, followed by 'SUMMARY'
    on its own line (required by Phase 3 template). We detect 'SUMMARY' as the
    anchor and walk back one paragraph break to include the name header.

    Returns:
        (review_block, final_cv) — either may be empty string on parse failure.
    """
    match = re.search(r"(?m)^SUMMARY$", phase35_output)
    if not match:
        log.warning("cv_generate: SUMMARY not found in Phase 3.5 output")
        return "", phase35_output.strip()

    before_summary = phase35_output[: match.start()]

    # Strip trailing newlines: before_summary ends with \n\n (the blank line before SUMMARY).
    # rfind on the raw string would hit that trailing \n\n and return an empty name_block.
    # Stripping first makes rfind find the \n\n between the review block and the name block.
    before_stripped = before_summary.rstrip("\n")
    last_para_break = before_stripped.rfind("\n\n")

    if last_para_break != -1:
        review = before_stripped[:last_para_break].strip()
        # name/headline/contacts block: between last_para_break and SUMMARY
        name_block = before_stripped[last_para_break + 2 :].strip()
        cv = name_block + "\n\n" + phase35_output[match.start():]
    else:
        # No paragraph break — treat everything before SUMMARY as the name block
        review = ""
        cv = phase35_output.strip()

    return review, cv.strip()
