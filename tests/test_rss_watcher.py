"""
tests/test_rss_watcher.py — tests for core/rss_watcher.py.

Mocks: database.list_vacancies, cv_fetch_jd, telegram_bot.send_message.
No real network, Telegram, or DB needed.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.rss_watcher import RSSWatcher, _read_seen_jobs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_entry(url: str, title: str = "", seen_at: str = "2026-05-29T17:00:00") -> dict:
    return {"url": url, "title": title, "seen_at": seen_at}


def _write_seen_jobs(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_watcher(tmp_path: Path, poll_interval: int = 1) -> tuple[RSSWatcher, MagicMock]:
    seen_jobs = tmp_path / "seen_jobs.json"
    deps = MagicMock()
    bot = MagicMock()
    bot.send_message = AsyncMock()
    watcher = RSSWatcher(
        seen_jobs_path=seen_jobs,
        deps=deps,
        telegram_bot=bot,
        poll_interval=poll_interval,
    )
    return watcher, bot


def _mock_db(known_urls: list[str]) -> MagicMock:
    db = MagicMock()
    rows = []
    for url in known_urls:
        row = MagicMock()
        row.__getitem__ = lambda self, key, u=url: u if key == "url" else None
        rows.append(row)
    db.list_vacancies = AsyncMock(return_value=rows)
    return db


# ── _read_seen_jobs ───────────────────────────────────────────────────────────

def test_read_seen_jobs_valid(tmp_path):
    path = tmp_path / "seen_jobs.json"
    entries = [_make_entry("https://djinni.co/jobs/1/"), _make_entry("https://djinni.co/jobs/2/")]
    _write_seen_jobs(path, entries)
    result = _read_seen_jobs(path)
    assert len(result) == 2
    assert result[0]["url"] == "https://djinni.co/jobs/1/"


def test_read_seen_jobs_missing_file(tmp_path):
    path = tmp_path / "nonexistent.json"
    assert _read_seen_jobs(path) == []


def test_read_seen_jobs_invalid_json(tmp_path):
    path = tmp_path / "seen_jobs.json"
    path.write_text("not valid json", encoding="utf-8")
    assert _read_seen_jobs(path) == []


def test_read_seen_jobs_not_a_list(tmp_path):
    path = tmp_path / "seen_jobs.json"
    path.write_text('{"url": "https://djinni.co/jobs/1/"}', encoding="utf-8")
    assert _read_seen_jobs(path) == []


def test_read_seen_jobs_empty_list(tmp_path):
    path = tmp_path / "seen_jobs.json"
    path.write_text("[]", encoding="utf-8")
    assert _read_seen_jobs(path) == []


# ── RSSWatcher.start — seeds known URLs ──────────────────────────────────────

@pytest.mark.asyncio
async def test_watcher_seeds_known_urls_from_db(tmp_path):
    watcher, _ = _make_watcher(tmp_path)
    mock_db = _mock_db(["https://djinni.co/jobs/known/"])

    with patch("core.rss_watcher.database", mock_db):
        await watcher.start()
        await watcher.stop()

    assert "https://djinni.co/jobs/known/" in watcher._seen_urls


@pytest.mark.asyncio
async def test_watcher_start_stop_clean(tmp_path):
    watcher, _ = _make_watcher(tmp_path)
    mock_db = _mock_db([])

    with patch("core.rss_watcher.database", mock_db):
        await watcher.start()
        await watcher.stop()

    assert watcher._task is not None
    assert watcher._task.done()


# ── RSSWatcher._poll_once — detects new URLs ─────────────────────────────────

@pytest.mark.asyncio
async def test_poll_once_triggers_fetch_for_new_url(tmp_path):
    seen_jobs = tmp_path / "seen_jobs.json"
    _write_seen_jobs(seen_jobs, [_make_entry("https://djinni.co/jobs/42/")])

    watcher, bot = _make_watcher(tmp_path)
    watcher._seen_urls = set()  # nothing known yet

    fetch_result = "✅ Вакансия сохранена! Backend Dev"
    mock_fetch = AsyncMock(return_value=fetch_result)

    with patch("tools.cv_fetch_jd.cv_fetch_jd", mock_fetch):
        with patch("core.rss_watcher.database", _mock_db([])):
            await watcher._poll_once()

    bot.send_message.assert_awaited_once()
    call_arg = bot.send_message.call_args[0][0]
    assert "Новая вакансия из RSS" in call_arg
    assert fetch_result in call_arg


@pytest.mark.asyncio
async def test_poll_once_skips_already_seen(tmp_path):
    seen_jobs = tmp_path / "seen_jobs.json"
    url = "https://djinni.co/jobs/known/"
    _write_seen_jobs(seen_jobs, [_make_entry(url)])

    watcher, bot = _make_watcher(tmp_path)
    watcher._seen_urls = {url}  # already known

    await watcher._poll_once()

    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_poll_once_adds_url_to_seen(tmp_path):
    seen_jobs = tmp_path / "seen_jobs.json"
    url = "https://djinni.co/jobs/99/"
    _write_seen_jobs(seen_jobs, [_make_entry(url)])

    watcher, _ = _make_watcher(tmp_path)
    watcher._seen_urls = set()

    mock_fetch = AsyncMock(return_value="✅ Done")
    with patch("tools.cv_fetch_jd.cv_fetch_jd", mock_fetch):
        await watcher._poll_once()

    assert url in watcher._seen_urls


@pytest.mark.asyncio
async def test_poll_once_empty_file(tmp_path):
    seen_jobs = tmp_path / "seen_jobs.json"
    _write_seen_jobs(seen_jobs, [])

    watcher, bot = _make_watcher(tmp_path)
    watcher._seen_urls = set()

    await watcher._poll_once()

    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_poll_once_missing_file(tmp_path):
    """seen_jobs.json does not exist — poll silently returns."""
    watcher, bot = _make_watcher(tmp_path)
    watcher._seen_urls = set()

    await watcher._poll_once()

    bot.send_message.assert_not_awaited()


# ── RSSWatcher._process — error handling ─────────────────────────────────────

@pytest.mark.asyncio
async def test_process_fetch_error_sends_warning(tmp_path):
    watcher, bot = _make_watcher(tmp_path)
    url = "https://djinni.co/jobs/bad/"

    mock_fetch = AsyncMock(side_effect=Exception("KMP connection refused"))
    with patch("tools.cv_fetch_jd.cv_fetch_jd", mock_fetch):
        await watcher._process(url)

    bot.send_message.assert_awaited_once()
    call_arg = bot.send_message.call_args[0][0]
    assert "⚠️" in call_arg
    assert "ошибка" in call_arg.lower()
