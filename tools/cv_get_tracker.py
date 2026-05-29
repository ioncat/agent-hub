"""
tools/cv_get_tracker.py — Tracker summary: SQLite vacancies → Telegram message.

Reads vacancies from DB (latest N, optional status filter).
For each vacancy that has JD_analysis.md, extracts fit score from the Quick Scan block.
No LLM call — pure DB + filesystem.

Output example:
    📊 Трекер вакансий — 3 записи

    1. ✅ cover_generated — Backend Dev [djinni] · Fit 8/10 · 2026-05-29
    2. 🔬 analyzed — Product Manager [djinni] · Fit 7/10 · 2026-05-28
    3. 📄 fetched — iOS Developer [dou] · — · 2026-05-27

Tool registered in agent.py via ToolRegistry.
Receives shared dependencies via RunContext[AgentDeps].
"""

import logging
import re
from pathlib import Path

from pydantic_ai import RunContext

from core.deps import AgentDeps
from db import database

log = logging.getLogger(__name__)

# Status → display label + emoji
_STATUS_EMOJI: dict[str, str] = {
    "fetched": "📄",
    "analyzed": "🔬",
    "cv_generated": "📝",
    "cover_generated": "✅",
    "error": "❌",
}

# Regex for "**Fit score:** 8/10" in JD_analysis.md Quick Scan block
_FIT_RE = re.compile(r"\*\*Fit score:\*\*\s*(\d+/\d+)", re.IGNORECASE)


async def cv_get_tracker(
    ctx: RunContext[AgentDeps],
    limit: int = 20,
    status: str | None = None,
) -> str:
    """Return a formatted summary of recent vacancies from the DB.

    Reads vacancies ordered by created_at DESC. For each vacancy that has
    JD_analysis.md on disk, extracts the fit score from the Quick Scan block.

    Args:
        limit:  Maximum number of vacancies to show (default 20).
        status: Optional filter — only show vacancies with this status.
                E.g. 'analyzed', 'cv_generated', 'cover_generated', 'error'.

    Returns:
        Formatted Telegram message with vacancy list.
    """
    log.info("cv_get_tracker: limit=%d status=%s", limit, status)

    rows = await database.list_vacancies(status=status, limit=limit)

    if not rows:
        if status:
            return (
                f"📊 Нет вакансий со статусом <b>{status}</b>.\n\n"
                f"Попробуй без фильтра или добавь вакансию командой fetch."
            )
        return (
            "📊 База вакансий пуста.\n\n"
            "Используй fetch чтобы добавить первую вакансию."
        )

    lines: list[str] = [f"📊 Трекер вакансий — {len(rows)} запис{'ь' if len(rows) == 1 else 'и' if 2 <= len(rows) <= 4 else 'ей'}\n"]

    for idx, row in enumerate(rows, 1):
        lines.append(_format_row(idx, row))

    return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_row(idx: int, row: object) -> str:
    """Format one vacancy row as a single tracker line."""
    status: str = row["status"] or "fetched"  # type: ignore[index]
    emoji = _STATUS_EMOJI.get(status, "❓")
    title: str = row["title"] or "Без названия"  # type: ignore[index]
    site: str = row["site"] or "?"  # type: ignore[index]
    created_at: str = row["created_at"] or ""  # type: ignore[index]
    date = created_at[:10]  # "YYYY-MM-DD"
    markdown_path: str | None = row["markdown_path"]  # type: ignore[index]

    fit = _extract_fit_score(markdown_path)

    return f"{idx}. {emoji} {status} — {title} [{site}] · Fit {fit} · {date}"


def _extract_fit_score(markdown_path: str | None) -> str:
    """Read JD_analysis.md next to JD.md and extract '**Fit score:** X/10'.

    Returns the score string (e.g. '8/10') or '—' if file missing or no match.
    Failures are silently ignored — tracker must never crash on missing files.
    """
    if not markdown_path:
        return "—"

    analysis_path = Path(markdown_path).parent / "JD_analysis.md"
    if not analysis_path.exists():
        return "—"

    try:
        text = analysis_path.read_text(encoding="utf-8")
        match = _FIT_RE.search(text)
        if match:
            return match.group(1)
    except OSError as exc:
        log.warning("cv_get_tracker: could not read %s: %s", analysis_path, exc)

    return "—"
