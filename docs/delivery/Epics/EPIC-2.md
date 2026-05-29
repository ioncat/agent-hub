# Epic 2: Database Layer

**Status:** 🟡 In Progress
**Phase:** 1 — Core Infrastructure
**Priority:** 🔴 P0 — BLOCKER
**Blocks:** EPIC-7 (cv_fetch_jd), EPIC-12 (Web Tracker), all pipeline tools

---

## Strategic Context

All CV pipeline tools need to track vacancy state (fetched → analyzed → CV generated → sent).
Without a DB layer there's no way to query "what's in flight", "what failed", or display the web tracker.
SQLite chosen for simplicity: single file, zero infra, async via aiosqlite.

---

## Goal

`db/schema.sql` defines tables. `db/database.py` exposes async `init_db()` and `get_db()` context manager.
All pipeline tools write/read only through `db/database.py` — never raw SQL elsewhere.

---

## Schema

```sql
-- vacancies: one row per unique job URL
CREATE TABLE vacancies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT    NOT NULL UNIQUE,
    title        TEXT,
    site         TEXT,                  -- 'djinni' | 'dou' | 'linkedin' | 'other'
    markdown_path TEXT,                 -- rel path to JD.md on filesystem
    status       TEXT    NOT NULL DEFAULT 'fetched',
                                        -- fetched | analyzing | analyzed | generating | done | error
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- pipeline_runs: one row per phase execution per vacancy
CREATE TABLE pipeline_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vacancy_id    INTEGER NOT NULL REFERENCES vacancies(id) ON DELETE CASCADE,
    phase         TEXT    NOT NULL,     -- 'phase1' | 'phase2' | 'phase3' | 'phase3_5' | 'phase4'
    status        TEXT    NOT NULL DEFAULT 'pending',
                                        -- pending | running | done | error
    result_path   TEXT,                 -- path to output file (analysis.md, cv.pdf, etc.)
    error_message TEXT,
    started_at    TEXT,
    finished_at   TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

---

## User Stories

### US-201: Schema initialisation

**Given** agent-hub starts for the first time
**When** `init_db()` is called
**Then** `vacancies` and `pipeline_runs` tables exist; second call is idempotent (CREATE IF NOT EXISTS)

---

### US-202: Async DB context manager

**Given** a pipeline tool needs to write or read
**When** it calls `async with get_db() as db:`
**Then** it gets an `aiosqlite.Connection` with `row_factory = sqlite3.Row`; connection is closed after block

---

### US-203: Vacancy CRUD helpers

Helper functions in `db/database.py`:
- `insert_vacancy(url, title, site, markdown_path) → int` (returns id)
- `get_vacancy_by_url(url) → sqlite3.Row | None`
- `update_vacancy_status(vacancy_id, status)`

---

### US-204: Pipeline run helpers

- `insert_pipeline_run(vacancy_id, phase) → int`
- `update_pipeline_run(run_id, status, result_path=None, error_message=None)`

---

## Implementation Plan

1. 🔴 Create `db/schema.sql` — tables `vacancies` + `pipeline_runs`
2. 🔴 Create `db/database.py` — `init_db()`, `get_db()`, CRUD helpers
3. 🟡 `db/` path read from `config/profile.yaml` via `settings.db_path`
4. 🟡 `agent.py` calls `await init_db()` on startup

---

## Open Questions

- [ ] DB path: hardcode `db/agent.db` for now, make configurable later?
- [ ] Migrations: use raw `ALTER TABLE` when schema changes, or add alembic in Phase 3?

---

## Acceptance Criteria

- `await init_db()` creates DB file + tables; second call no-ops
- `async with get_db() as db:` returns working aiosqlite connection
- All CRUD helpers tested via contract test in `tests/test_db.py`
