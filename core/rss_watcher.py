"""
core/rss_watcher.py — Background watcher: polls DB for queued vacancies, triggers cv_fetch_jd.

New vacancies arrive via POST /api/new-vacancy (from job-monitor service) which
inserts them into the DB with status='queued'. This watcher picks them up and
runs the fetch+parse pipeline.

Replaces the old file-polling approach (seen_jobs.json) with DB-based event delivery.

Lifecycle (in agent.py):
    watcher = RSSWatcher(deps, bot, poll_interval=30)
    await watcher.start()
    # ... bot runs ...
    await watcher.stop()
"""

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass

from core.deps import AgentDeps
from db import database

log = logging.getLogger(__name__)


@dataclass
class _Ctx:
    """Minimal RunContext[AgentDeps] stand-in for calling tools outside PydanticAI agent."""
    deps: AgentDeps


class RSSWatcher:
    """Polls DB for status='queued' vacancies and triggers cv_fetch_jd for each.

    Runs as a background asyncio.Task. Vacancies are inserted by the
    POST /api/new-vacancy endpoint (job-monitor webhook).
    """

    def __init__(
        self,
        deps: AgentDeps,
        telegram_bot: object,   # TelegramBot — avoids circular import
        poll_interval: int = 30,
    ) -> None:
        self._deps = deps
        self._bot = telegram_bot
        self._interval = poll_interval
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Launch background polling task."""
        self._task = asyncio.create_task(self._run(), name="rss-watcher")
        log.info(
            "RSSWatcher: started — polling DB for queued vacancies every %ds",
            self._interval,
        )

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
                log.error("RSSWatcher: unexpected error in poll loop: %s", exc)

    async def _poll_once(self) -> None:
        """Query DB for queued vacancies and process each."""
        rows = await database.list_vacancies(
            status="queued",
            user_id=self._deps.user_id,
        )
        if not rows:
            return

        log.info("RSSWatcher: %d queued vacancy(s) found", len(rows))
        for row in rows:
            url = row["url"]
            vacancy_id = row["id"]
            # Claim the vacancy immediately to avoid double-processing
            await database.update_vacancy_status(vacancy_id, "fetching")
            await self._process(url)

    async def _process(self, url: str) -> None:
        """Fetch one vacancy and send the result to Telegram."""
        from tools.cv_fetch_jd import cv_fetch_jd  # local import to avoid circular

        log.info("RSSWatcher: fetching vacancy — %s", url)
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
