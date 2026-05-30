"""
db/database.py — async SQLite layer via aiosqlite.

All DB access in agent-hub goes through this module.
Never write raw SQL in tools or adapters — use helpers here.

Usage:
    # startup
    await init_db()

    # read/write
    async with get_db() as db:
        row = await db.execute("SELECT * FROM vacancies WHERE id = ?", (vid,))
        ...
"""

import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

log = logging.getLogger(__name__)

# Default DB path — override via DB_PATH env var or settings
_DEFAULT_DB_PATH = Path(__file__).parent / "agent.db"
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_db_path: Path = _DEFAULT_DB_PATH


def configure(db_path: str | Path) -> None:
    """Set DB path before first call to init_db(). Called from agent.py on startup."""
    global _db_path
    _db_path = Path(db_path)


async def init_db() -> None:
    """Create DB file and apply schema. Idempotent — safe to call on every startup."""
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")

    async with aiosqlite.connect(_db_path) as db:
        await db.executescript(schema)
        # Migrations: add columns introduced after initial schema
        for migration in [
            "ALTER TABLE vacancies ADD COLUMN warnings TEXT NOT NULL DEFAULT ''",
            # llm_usage granular breakdown (added after initial schema)
            "ALTER TABLE llm_usage ADD COLUMN profile_tokens  INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE llm_usage ADD COLUMN prompt_tokens   INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE llm_usage ADD COLUMN user_tokens     INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE llm_usage ADD COLUMN budget_tokens   INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE llm_usage ADD COLUMN thinking_tokens INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE llm_usage ADD COLUMN elapsed_ms      INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                await db.execute(migration)
                await db.commit()
                log.info("DB migration applied: %s", migration[:60])
            except Exception:
                pass  # column already exists — ignore

    log.info("DB initialised at %s", _db_path)


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager: yields open aiosqlite connection with Row factory."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db


# ── Vacancy helpers ───────────────────────────────────────────────────────────

async def insert_vacancy(
    url: str,
    title: str | None = None,
    site: str | None = None,
    markdown_path: str | None = None,
) -> int:
    """Insert new vacancy. Returns new row id.

    Raises sqlite3.IntegrityError if URL already exists — caller should handle.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO vacancies (url, title, site, markdown_path)
            VALUES (?, ?, ?, ?)
            """,
            (url, title, site, markdown_path),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_vacancy_by_url(url: str) -> aiosqlite.Row | None:
    """Return vacancy row by URL or None if not found."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM vacancies WHERE url = ?", (url,)
        )
        return await cursor.fetchone()


async def get_vacancy_by_id(vacancy_id: int) -> aiosqlite.Row | None:
    """Return vacancy row by id or None if not found."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM vacancies WHERE id = ?", (vacancy_id,)
        )
        return await cursor.fetchone()


async def update_vacancy_warnings(vacancy_id: int, warnings: str) -> None:
    """Store semicolon-separated warnings for a vacancy."""
    async with get_db() as db:
        await db.execute(
            "UPDATE vacancies SET warnings = ? WHERE id = ?",
            (warnings, vacancy_id),
        )
        await db.commit()


async def update_vacancy_status(vacancy_id: int, status: str) -> None:
    """Update vacancy status and bump updated_at."""
    log.info("DB: vacancy #%d status → %s", vacancy_id, status)
    async with get_db() as db:
        await db.execute(
            """
            UPDATE vacancies
            SET status = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, vacancy_id),
        )
        await db.commit()


async def list_vacancies(status: str | None = None, limit: int = 50) -> list[aiosqlite.Row]:
    """Return vacancies ordered by created_at desc. Optionally filter by status."""
    async with get_db() as db:
        if status:
            cursor = await db.execute(
                "SELECT * FROM vacancies WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM vacancies ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return await cursor.fetchall()


# ── Pipeline run helpers ───────────────────────────────────────────────────────

async def insert_pipeline_run(vacancy_id: int, phase: str) -> int:
    """Create a new pipeline run record in 'pending' state. Returns run id."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO pipeline_runs (vacancy_id, phase, status)
            VALUES (?, ?, 'pending')
            """,
            (vacancy_id, phase),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def update_pipeline_run(
    run_id: int,
    status: str,
    result_path: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update pipeline run status, optionally set result_path or error.

    Sets started_at on first transition to 'running'.
    Sets finished_at when status is 'done' or 'error'.
    """
    async with get_db() as db:
        # Fetch current status to decide timestamp updates
        cur = await db.execute("SELECT status FROM pipeline_runs WHERE id = ?", (run_id,))
        row = await cur.fetchone()
        current = row["status"] if row else None

        started_at_expr = "started_at"
        finished_at_expr = "finished_at"

        if status == "running" and current == "pending":
            started_at_expr = "datetime('now')"
        if status in ("done", "error"):
            finished_at_expr = "datetime('now')"

        if status == "error":
            log.error("DB: pipeline_run #%d → error: %s", run_id, error_message or "(no message)")
        elif status == "done":
            log.info("DB: pipeline_run #%d → done (result=%s)", run_id, result_path)

        await db.execute(
            f"""
            UPDATE pipeline_runs
            SET status        = ?,
                result_path   = COALESCE(?, result_path),
                error_message = COALESCE(?, error_message),
                started_at    = {started_at_expr},
                finished_at   = {finished_at_expr}
            WHERE id = ?
            """,
            (status, result_path, error_message, run_id),
        )
        await db.commit()


async def insert_llm_usage(
    phase: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
    cost_usd: float,
    vacancy_id: int | None = None,
    profile_tokens: int = 0,
    prompt_tokens: int = 0,
    user_tokens: int = 0,
    budget_tokens: int = 0,
    thinking_tokens: int = 0,
    elapsed_ms: int = 0,
) -> int:
    """Record one LLM API call for cost tracking and unit economics analysis.

    Input breakdown (profile/prompt/user) is estimated from text length (len//4, ±10%).
    API-reported totals (input/output/cache) are exact from the response.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO llm_usage
                (vacancy_id, phase, model,
                 profile_tokens, prompt_tokens, user_tokens,
                 input_tokens, output_tokens,
                 cache_write_tokens, cache_read_tokens,
                 budget_tokens, thinking_tokens,
                 elapsed_ms, cost_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (vacancy_id, phase, model,
             profile_tokens, prompt_tokens, user_tokens,
             input_tokens, output_tokens,
             cache_write_tokens, cache_read_tokens,
             budget_tokens, thinking_tokens,
             elapsed_ms, round(cost_usd, 6)),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_pipeline_runs(vacancy_id: int) -> list[aiosqlite.Row]:
    """Return all pipeline runs for a vacancy, ordered by phase."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM pipeline_runs
            WHERE vacancy_id = ?
            ORDER BY created_at ASC
            """,
            (vacancy_id,),
        )
        return await cursor.fetchall()
