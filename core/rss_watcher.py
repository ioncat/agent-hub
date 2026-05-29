"""
core/rss_watcher.py — Background RSS watcher: polls seen_jobs.json, triggers cv_fetch_jd.

Simulates the RSS channel from job-board-monitor. When a new URL appears in
seen_jobs.json, fetches the vacancy and sends the result to Telegram.

seen_jobs.json format (produced by job-board-monitor or scripts/emit_vacancy.py):
    [
        {
            "url": "https://djinni.co/jobs/123/",
            "title": "Backend Developer",
            "seen_at": "2026-05-29T17:00:00"
        },
        ...
    ]

Lifecycle (in agent.py):
    watcher = RSSWatcher(settings.seen_jobs_path, deps, bot, settings.rss_poll_interval)
    await watcher.start()   # seeds known URLs from DB, starts polling task
    # ... bot runs ...
    await watcher.stop()    # graceful cancel
"""

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from core.deps import AgentDeps
from db import database

log = logging.getLogger(__name__)


@dataclass
class _Ctx:
    """Minimal RunContext[AgentDeps] stand-in for calling tools outside PydanticAI agent."""
    deps: AgentDeps


class RSSWatcher:
    """Polls seen_jobs.json and triggers cv_fetch_jd for each new URL.

    Runs as a background asyncio.Task. Known URLs are seeded from the DB on
    startup so already-processed vacancies are never re-fetched after a restart.
    """

    def __init__(
        self,
        seen_jobs_path: Path,
        deps: AgentDeps,
        telegram_bot: object,   # TelegramBot — avoids circular import
        poll_interval: int = 60,
    ) -> None:
        self._path = Path(seen_jobs_path)
        self._deps = deps
        self._bot = telegram_bot
        self._interval = poll_interval
        self._seen_urls: set[str] = set()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Seed known URLs from DB, then launch background polling task."""
        existing = await database.list_vacancies(limit=10_000)
        self._seen_urls = {row["url"] for row in existing}
        log.info(
            "RSSWatcher: seeded %d known URLs — polling %s every %ds",
            len(self._seen_urls), self._path, self._interval,
        )
        self._task = asyncio.create_task(self._run(), name="rss-watcher")

    async def stop(self) -> None:
        """Cancel the polling task and wait for it to exit cleanly."""
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            log.info("RSSWatcher: stopped")

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _run(self) -> None:
        """Polling loop — runs until cancelled."""
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Never let the loop die on unexpected errors
                log.error("RSSWatcher: unexpected error in poll loop: %s", exc)

    async def _poll_once(self) -> None:
        """Read seen_jobs.json and process any URLs not yet in the known set."""
        entries = _read_seen_jobs(self._path)
        new_entries = [e for e in entries if e.get("url") not in self._seen_urls]

        if not new_entries:
            return

        log.info("RSSWatcher: %d new vacancies detected in %s", len(new_entries), self._path)
        for entry in new_entries:
            url = entry.get("url", "").strip()
            if not url:
                continue
            self._seen_urls.add(url)
            await self._process(url)

    async def _process(self, url: str) -> None:
        """Fetch one vacancy and send the result to Telegram."""
        from tools.cv_fetch_jd import cv_fetch_jd  # local import to avoid circular

        log.info("RSSWatcher: fetching new vacancy — %s", url)
        ctx = _Ctx(deps=self._deps)
        try:
            result = await cv_fetch_jd(ctx, url)  # type: ignore[arg-type]
            await self._bot.send_message(  # type: ignore[union-attr]
                f"🔔 <b>Новая вакансия из RSS</b>\n\n{result}"
            )
        except Exception as exc:
            log.error("RSSWatcher: failed to process %s: %s", url, exc)
            await self._bot.send_message(  # type: ignore[union-attr]
                f"⚠️ <b>RSS: ошибка при обработке вакансии</b>\n\n"
                f"URL: <code>{url}</code>\nОшибка: {exc}"
            )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_seen_jobs(path: Path) -> list[dict]:
    """Read seen_jobs.json and return its entries.

    Returns [] on any error (file missing, invalid JSON, wrong type).
    Never raises — the watcher must never crash on a bad file.
    """
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        log.warning("RSSWatcher: %s is not a JSON list — skipping", path)
        return []
    except (json.JSONDecodeError, OSError) as exc:
        log.error("RSSWatcher: failed to read %s: %s", path, exc)
        return []
