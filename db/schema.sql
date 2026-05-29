-- agent-hub SQLite schema
-- Applied via db/database.py:init_db() on startup
-- Never execute directly against a running DB — use init_db()

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── vacancies ────────────────────────────────────────────────────────────────
-- One row per unique job posting URL.
-- markdown_path: relative path from project root, e.g. "vacancies/djinni/2024-01/job-123/JD.md"

CREATE TABLE IF NOT EXISTS vacancies (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT    NOT NULL UNIQUE,
    title         TEXT,
    site          TEXT,                   -- 'djinni' | 'dou' | 'linkedin' | 'other'
    markdown_path TEXT,                   -- path to JD.md on filesystem
    status        TEXT    NOT NULL DEFAULT 'fetched',
                                          -- fetched | analyzing | analyzed | generating | done | error
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_vacancies_status ON vacancies (status);
CREATE INDEX IF NOT EXISTS idx_vacancies_site   ON vacancies (site);

-- ── pipeline_runs ─────────────────────────────────────────────────────────────
-- One row per phase execution attempt per vacancy.
-- result_path: path to output artifact (analysis.md, cv.pdf, etc.)

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vacancy_id    INTEGER NOT NULL REFERENCES vacancies(id) ON DELETE CASCADE,
    phase         TEXT    NOT NULL,       -- 'phase1' | 'phase2' | 'phase3' | 'phase3_5' | 'phase4'
    status        TEXT    NOT NULL DEFAULT 'pending',
                                          -- pending | running | done | error
    result_path   TEXT,
    error_message TEXT,
    started_at    TEXT,
    finished_at   TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pipeline_vacancy ON pipeline_runs (vacancy_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_status  ON pipeline_runs (status);
