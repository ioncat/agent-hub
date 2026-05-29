"""
tests/test_cv_get_tracker.py — tests for tools/cv_get_tracker.py.

Mocks: database.list_vacancies, filesystem (tmp_path for JD_analysis.md).
No real DB, LLM, or network needed.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.cv_get_tracker import _extract_fit_score, _format_row, cv_get_tracker


# ── Fixtures / helpers ────────────────────────────────────────────────────────

def _make_ctx(tmp_path: Path | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.deps.vacancies_path = (tmp_path or Path("/fake")) / "vacancies"
    return ctx


def _make_row(
    vacancy_id: int = 1,
    title: str = "Backend Dev",
    site: str = "djinni",
    status: str = "analyzed",
    markdown_path: str | None = None,
    created_at: str = "2026-05-29 17:00:00",
) -> MagicMock:
    data = {
        "id": vacancy_id,
        "title": title,
        "site": site,
        "status": status,
        "markdown_path": markdown_path,
        "url": f"https://djinni.co/jobs/{vacancy_id}/",
        "created_at": created_at,
        "updated_at": created_at,
    }
    row = MagicMock()
    row.__getitem__ = lambda self, key: data[key]
    return row


def _mock_db(rows: list) -> MagicMock:
    db = MagicMock()
    db.list_vacancies = AsyncMock(return_value=rows)
    return db


def _write_analysis(tmp_path: Path, fit_score: str = "8/10") -> Path:
    """Create a minimal JD_analysis.md with a fit score line; return JD.md path."""
    jd_dir = tmp_path / "vacancies" / "djinni" / "2026-05" / "123"
    jd_dir.mkdir(parents=True)
    jd_path = jd_dir / "JD.md"
    jd_path.write_text("# Backend Dev", encoding="utf-8")
    analysis = jd_dir / "JD_analysis.md"
    analysis.write_text(f"## Quick Scan\n\n**Fit score:** {fit_score}\n", encoding="utf-8")
    return jd_path


# ── _extract_fit_score ────────────────────────────────────────────────────────

def test_extract_fit_score_found(tmp_path):
    jd_path = _write_analysis(tmp_path, fit_score="7/10")
    assert _extract_fit_score(str(jd_path)) == "7/10"


def test_extract_fit_score_no_file(tmp_path):
    missing = tmp_path / "vacancies" / "djinni" / "2026-05" / "999" / "JD.md"
    assert _extract_fit_score(str(missing)) == "—"


def test_extract_fit_score_none_path():
    assert _extract_fit_score(None) == "—"


def test_extract_fit_score_no_match(tmp_path):
    jd_dir = tmp_path / "vacancies" / "djinni" / "2026-05" / "321"
    jd_dir.mkdir(parents=True)
    jd_path = jd_dir / "JD.md"
    jd_path.write_text("# Dev", encoding="utf-8")
    (jd_dir / "JD_analysis.md").write_text("## Phase 1\n\nNo fit score here.", encoding="utf-8")
    assert _extract_fit_score(str(jd_path)) == "—"


# ── _format_row ───────────────────────────────────────────────────────────────

def test_format_row_cover_generated():
    row = _make_row(status="cover_generated", title="PM Lead", site="dou")
    line = _format_row(1, row)
    assert "✅" in line
    assert "PM Lead" in line
    assert "dou" in line
    assert "cover_generated" in line


def test_format_row_analyzed():
    row = _make_row(status="analyzed")
    line = _format_row(2, row)
    assert "🔬" in line


def test_format_row_error_emoji():
    row = _make_row(status="error")
    line = _format_row(1, row)
    assert "❌" in line


def test_format_row_date_extracted():
    row = _make_row(created_at="2026-05-28 10:00:00")
    line = _format_row(1, row)
    assert "2026-05-28" in line


def test_format_row_no_markdown_path_shows_dash():
    row = _make_row(markdown_path=None)
    line = _format_row(1, row)
    assert "—" in line


# ── cv_get_tracker — happy path ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tracker_happy_path(tmp_path):
    rows = [
        _make_row(1, title="Backend Dev", status="cover_generated"),
        _make_row(2, title="Product Manager", status="analyzed"),
    ]
    ctx = _make_ctx(tmp_path)
    mock_db = _mock_db(rows)

    with patch("tools.cv_get_tracker.database", mock_db):
        result = await cv_get_tracker(ctx)

    assert "📊" in result
    assert "Backend Dev" in result
    assert "Product Manager" in result


@pytest.mark.asyncio
async def test_tracker_shows_all_rows(tmp_path):
    rows = [_make_row(i, title=f"Job {i}") for i in range(1, 6)]
    ctx = _make_ctx(tmp_path)
    mock_db = _mock_db(rows)

    with patch("tools.cv_get_tracker.database", mock_db):
        result = await cv_get_tracker(ctx)

    for i in range(1, 6):
        assert f"Job {i}" in result


@pytest.mark.asyncio
async def test_tracker_passes_limit_to_db(tmp_path):
    ctx = _make_ctx(tmp_path)
    mock_db = _mock_db([])

    with patch("tools.cv_get_tracker.database", mock_db):
        await cv_get_tracker(ctx, limit=5)

    mock_db.list_vacancies.assert_awaited_once_with(status=None, limit=5)


@pytest.mark.asyncio
async def test_tracker_passes_status_filter(tmp_path):
    ctx = _make_ctx(tmp_path)
    mock_db = _mock_db([])

    with patch("tools.cv_get_tracker.database", mock_db):
        await cv_get_tracker(ctx, status="analyzed")

    mock_db.list_vacancies.assert_awaited_once_with(status="analyzed", limit=20)


@pytest.mark.asyncio
async def test_tracker_fit_score_from_file(tmp_path):
    jd_path = _write_analysis(tmp_path, fit_score="9/10")
    rows = [_make_row(1, markdown_path=str(jd_path), status="analyzed")]
    ctx = _make_ctx(tmp_path)
    mock_db = _mock_db(rows)

    with patch("tools.cv_get_tracker.database", mock_db):
        result = await cv_get_tracker(ctx)

    assert "9/10" in result


@pytest.mark.asyncio
async def test_tracker_fit_score_dash_when_no_analysis(tmp_path):
    rows = [_make_row(1, markdown_path=str(tmp_path / "missing" / "JD.md"))]
    ctx = _make_ctx(tmp_path)
    mock_db = _mock_db(rows)

    with patch("tools.cv_get_tracker.database", mock_db):
        result = await cv_get_tracker(ctx)

    assert "—" in result


# ── cv_get_tracker — empty / edge cases ──────────────────────────────────────

@pytest.mark.asyncio
async def test_tracker_empty_db(tmp_path):
    ctx = _make_ctx(tmp_path)
    mock_db = _mock_db([])

    with patch("tools.cv_get_tracker.database", mock_db):
        result = await cv_get_tracker(ctx)

    assert "📊" in result
    assert "пуста" in result.lower() or "пуст" in result.lower()


@pytest.mark.asyncio
async def test_tracker_empty_with_status_filter(tmp_path):
    ctx = _make_ctx(tmp_path)
    mock_db = _mock_db([])

    with patch("tools.cv_get_tracker.database", mock_db):
        result = await cv_get_tracker(ctx, status="error")

    assert "error" in result
    assert "📊" in result


@pytest.mark.asyncio
async def test_tracker_row_count_in_header(tmp_path):
    rows = [_make_row(i) for i in range(1, 4)]
    ctx = _make_ctx(tmp_path)
    mock_db = _mock_db(rows)

    with patch("tools.cv_get_tracker.database", mock_db):
        result = await cv_get_tracker(ctx)

    assert "3" in result
