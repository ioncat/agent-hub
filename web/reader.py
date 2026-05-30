"""
web/reader.py — Read JD_analysis.md and build VacancyView for the web tracker.

Parses Quick Scan fields (fit score, recommendation, category, warnings, blockers)
from JD_analysis.md via regex. Full markdown passed to template for client-side
rendering via marked.js.

All parsing is best-effort: missing fields return empty strings, never raises.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Regexes for Quick Scan fields ────────────────────────────────────────────
_FIT_RE   = re.compile(r"\*\*Fit score:\*\*\s*(.+?)(?:\n|$)", re.IGNORECASE)
_REC_RE   = re.compile(r"\*\*Recommendation:\*\*\s*(.+?)(?:\n|$)", re.IGNORECASE)
_CAT_RE   = re.compile(r"\*\*Category:\*\*\s*(.+?)(?:\n|$)", re.IGNORECASE)
_WARN_RE  = re.compile(r"\*\*Warnings:\*\*\s*(.+?)(?:\n|$)", re.IGNORECASE)
_BLOCK_RE = re.compile(r"\*\*Blockers:\*\*\s*(.+?)(?:\n|$)", re.IGNORECASE)

# Statuses that imply the given artifact exists
_STATUS_ORDER = ["fetched", "analyzed", "cv_generated", "cover_generated"]


def _status_gte(status: str, threshold: str) -> bool:
    """Return True if status is at or after threshold in pipeline order."""
    try:
        return _STATUS_ORDER.index(status) >= _STATUS_ORDER.index(threshold)
    except ValueError:
        return False


@dataclass
class VacancyView:
    """All display data for one vacancy row in the web tracker."""
    id: int
    title: str
    url: str
    site: str
    status: str
    date: str               # "YYYY-MM-DD" from created_at
    fit_score: str          # "8/10" or "—"
    recommendation: str     # "подавать" / "не подавать" / ""
    category: str           # "AI Product · Remote" or ""
    warnings: str           # raw semicolon-separated warnings
    blockers: str           # raw blockers text
    has_analysis: bool
    has_cv: bool
    has_cover: bool
    has_pdf: bool
    analysis_md: str        # full JD_analysis.md content for marked.js rendering

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def rec_class(self) -> str:
        """CSS class for row left-border colour."""
        rec = self.recommendation.lower()
        if "не подавать" in rec or "not apply" in rec:
            return "rec-no"
        if "подавать" in rec or "apply" in rec:
            return "rec-yes"
        return ""

    @property
    def warn_count(self) -> int:
        """Number of distinct warnings (split by ';')."""
        if not self.warnings or self.warnings.strip() in ("нет", "none", "—", "-"):
            return 0
        return len([w for w in self.warnings.split(";") if w.strip()])

    @property
    def warn_text_escaped(self) -> str:
        """Warnings with single quotes escaped for inline onclick='showWarn(...)'."""
        return self.warnings.replace("'", "\\'").replace('"', "&quot;")


def build_vacancy_view(row: object, candidate_name: str = "Candidate") -> VacancyView:
    """Build VacancyView from a DB row (aiosqlite.Row or dict-like).

    Reads JD_analysis.md from disk if available. All errors are silently ignored.
    """
    vacancy_id: int = row["id"]  # type: ignore[index]
    title: str      = row["title"] or "Без названия"  # type: ignore[index]
    url: str        = row["url"] or ""  # type: ignore[index]
    site: str       = row["site"] or "?"  # type: ignore[index]
    status: str     = row["status"] or "fetched"  # type: ignore[index]
    created_at: str = row["created_at"] or ""  # type: ignore[index]
    markdown_path: str | None = row["markdown_path"]  # type: ignore[index]
    db_warnings: str = row["warnings"] if "warnings" in row.keys() else ""  # type: ignore[index]

    date = created_at[:10]  # "YYYY-MM-DD"
    safe_name = re.sub(r"[^\w\-]", "_", candidate_name)

    # ── Artifact paths ────────────────────────────────────────────────────────
    folder = Path(markdown_path).parent if markdown_path else None
    analysis_path = folder / "JD_analysis.md" if folder else None
    cv_md_path    = folder / f"{safe_name}_CV.md" if folder else None
    cv_pdf_path   = folder / f"{safe_name}_CV.pdf" if folder else None
    cover_path    = folder / f"{safe_name}_Cover.md" if folder else None

    has_analysis = bool(analysis_path and analysis_path.exists())
    has_cv       = bool(cv_md_path and cv_md_path.exists())
    has_cover    = bool(cover_path and cover_path.exists())
    has_pdf      = bool(cv_pdf_path and cv_pdf_path.exists())

    # ── Parse analysis fields ─────────────────────────────────────────────────
    analysis_md = ""
    fit_score = "—"
    recommendation = ""
    category = ""
    warnings = ""
    blockers = ""

    if has_analysis and analysis_path:
        try:
            analysis_md = analysis_path.read_text(encoding="utf-8")
            fit_score    = _extract(analysis_md, _FIT_RE) or "—"
            recommendation = _extract(analysis_md, _REC_RE)
            category     = _extract(analysis_md, _CAT_RE)
            warnings     = _extract(analysis_md, _WARN_RE)
            blockers     = _extract(analysis_md, _BLOCK_RE)
        except OSError:
            pass

    # Fallback: use DB warnings if JD_analysis.md didn't have the field
    if not warnings and db_warnings:
        warnings = db_warnings

    return VacancyView(
        id=vacancy_id,
        title=title,
        url=url,
        site=site,
        status=status,
        date=date,
        fit_score=fit_score,
        recommendation=recommendation,
        category=category,
        warnings=warnings,
        blockers=blockers,
        has_analysis=has_analysis,
        has_cv=has_cv,
        has_cover=has_cover,
        has_pdf=has_pdf,
        analysis_md=analysis_md,
    )


def _extract(text: str, pattern: re.Pattern) -> str:
    """Return first capture group stripped, or empty string."""
    m = pattern.search(text)
    return m.group(1).strip() if m else ""
