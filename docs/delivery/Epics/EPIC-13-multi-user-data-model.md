# EPIC-13 — Multi-user data model

**Status:** ✅ Done (2026-06-01)
**Phase:** Phase 1 of PIVOT-PLAN
**Priority:** P0 — Foundation
**Last updated:** 2026-06-01

---

## User Story

```
As a Career Agent operator
I want each candidate to have an isolated data namespace in the system
So that multiple job seekers can use the same instance without accessing each other's vacancies, analyses, or CV artifacts
```

---

## Acceptance Criteria

**Given** a new candidate contacts the bot for the first time
**When** they send any command
**Then** a user record is created in the `users` table with their Telegram `chat_id` and `skill_type`

**Given** a user submits a vacancy URL
**When** the vacancy is saved to DB
**Then** the vacancy row carries `user_id` FK linking it to that user

**Given** multiple users have submitted vacancies
**When** the web tracker loads vacancies
**Then** it shows only vacancies belonging to the selected user (filter by `user_id`)

**Given** the system restarts
**When** the default user's `telegram_chat_id` is in the DB
**Then** `get_or_create_default_user` returns the existing `user_id` without creating a duplicate

**Given** a user is created with `skill_type = 'pm'`
**When** any pipeline phase runs for that user
**Then** prompts are loaded from `prompts/pm/`

---

## Edge Cases

- Vacancy inserted without `user_id` (legacy/import) — `user_id = NULL`, treated as pre-multi-user data; must not break existing queries
- Two users submit the same URL — both get separate vacancy rows (URL UNIQUE constraint applies per user, or URL is shared — decision: URL is globally unique, `user_id` scopes analysis artifacts, not the vacancy row itself)
- `DEFAULT_SKILL_TYPE` env var not set → default `'pm'`
- `get_user_by_id` returns `None` for unknown id → graceful fallback to settings default

---

## Out of Scope

- Authentication / authorization (no login, no password) — Phase 5 (Onboarding)
- Per-user RSS feed configuration — Phase 5
- Web tracker auth — Phase 7
- `pipeline_runs` user_id FK — deferred (vacancies already carry user_id, runs join via vacancy)

---

## Notes for Engineering

- Migration strategy: `ALTER TABLE ... ADD COLUMN user_id` (nullable) — backward compat, existing rows get NULL
- `get_or_create_default_user` called in `agent.py` after `init_db()` — idempotent on every restart
- `AgentDeps.user_id` + `AgentDeps.skill_type` — source of truth for active session
- Vacancy filesystem path: `vacancies/[user_id]/[Company — Role]/` — scoped per user, created on first write
- `DEFAULT_SKILL_TYPE` env var overrides seeded skill_type only at first user creation; DB value takes precedence thereafter

---

## Dependencies

- None (foundation epic — all others depend on this)

---

## Tasks

| # | Task | Status |
|---|------|--------|
| 1 | `db/schema.sql` — `users` table (`id`, `telegram_chat_id`, `name`, `skill_type`, `created_at`) | ✅ Done |
| 2 | `db/database.py` — user CRUD: `insert_user`, `get_user_by_id`, `get_user_by_telegram_id`, `get_or_create_default_user`, `list_users`, `update_user_skill_type` | ✅ Done |
| 3 | `db/database.py` — `user_id` FK migration for `vacancies` + `llm_usage` (nullable, backward compat) | ✅ Done |
| 4 | `core/deps.py` — `AgentDeps` carries `user_id` (default=1) + `skill_type` (default=`'pm'`) | ✅ Done |
| 5 | `core/settings.py` — `DEFAULT_SKILL_TYPE` env var; `agent.py` seeds default user after `init_db()` | ✅ Done |
| 6 | Vacancy filesystem path scoped to `vacancies/[user_id]/[Company]/`; tools write to user-scoped path | ✅ Done |
| 7 | `web/api.py` — `GET /tracker?user_id=N` filter; `tracker.html` — user selector dropdown | ✅ Done |
| 8 | All tests pass with `user_id` param (236 tests currently green) | ✅ Done |
