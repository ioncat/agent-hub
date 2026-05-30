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
    warnings      TEXT    NOT NULL DEFAULT '',
                                          -- semicolon-separated soft flags (imported from tracker or analysis)
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

-- ── llm_usage ─────────────────────────────────────────────────────────────────
-- One row per LLM API call. Enables cost analysis per vacancy, per phase,
-- per model, and cache efficiency tracking (unit economics).

CREATE TABLE IF NOT EXISTS llm_usage (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    vacancy_id           INTEGER REFERENCES vacancies(id) ON DELETE SET NULL,
    phase                TEXT    NOT NULL,   -- 'phase1' | 'phase2' | 'phase3' | 'phase3_5' | 'phase4'
    model                TEXT    NOT NULL,
    input_tokens         INTEGER NOT NULL DEFAULT 0,
    output_tokens        INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens   INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens    INTEGER NOT NULL DEFAULT 0,
    cost_usd             REAL    NOT NULL DEFAULT 0.0,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_vacancy ON llm_usage (vacancy_id);
CREATE INDEX IF NOT EXISTS idx_llm_usage_phase   ON llm_usage (phase);
CREATE INDEX IF NOT EXISTS idx_llm_usage_date    ON llm_usage (created_at);
