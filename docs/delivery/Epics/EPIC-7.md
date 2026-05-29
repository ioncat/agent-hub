# Epic 7: CV Fetch JD Tool

**Status:** 🟢 Done
**Phase:** 2 — CV Pipeline
**Priority:** 🔴 P0 — BLOCKER
**Blocks:** EPIC-8 (cv_analyze), EPIC-9 (cv_generate)

---

## Strategic Context

First real pipeline step. User sends a vacancy URL → bot fetches and parses it via kmp-service,
saves JD.md to filesystem, registers vacancy in SQLite. Everything downstream (analysis, CV, cover)
depends on JD.md existing on disk and vacancy row in DB.

Also introduces `AgentDeps` — the shared dependency container passed to all PydanticAI tools
via `RunContext`. Pattern established here is reused in EPIC-8–11.

---

## Goal

`tools/cv_fetch_jd.py` exposes `cv_fetch_jd(ctx, url) → str`.
Registered in `agent.py` ToolRegistry. Callable by the PydanticAI router when user sends a URL.

---

## Folder Structure

```
vacancies/
└── {site}/            ← djinni | dou | linkedin | other
    └── YYYY-MM/       ← year-month of fetch
        └── {slug}/    ← sanitized URL path segment
            └── JD.md
```

---

## User Stories

### US-701: Fetch and save JD

**Given** user sends `https://djinni.co/jobs/123-backend-python/`
**When** `cv_fetch_jd` runs
**Then**:
- `KMPAdapter.fetch_markdown(url)` called → `ParsedDocument`
- `vacancies/djinni/2026-05/123-backend-python/JD.md` created
- Vacancy inserted into SQLite (`status=fetched`)
- Telegram reply: title + path + "✅ Готово. Запускаем анализ?"

### US-702: Duplicate URL

**Given** URL already in DB
**When** `cv_fetch_jd` runs
**Then** skip fetch, return existing vacancy info with path

### US-703: kmp-service error

**Given** kmp-service is down or returns 503
**When** `cv_fetch_jd` runs
**Then** return user-friendly error "⚠️ Не удалось получить вакансию: ..."

---

## Implementation Plan

1. 🔴 `core/deps.py` — `AgentDeps` dataclass (KMPAdapter, LLM client, paths)
2. 🔴 Update `core/router.py` — accept AgentDeps, pass deps to Agent.run()
3. 🔴 Update `core/settings.py` — add vacancies_path
4. 🔴 Update `agent.py` — build AgentDeps
5. 🔴 `tools/cv_fetch_jd.py` — tool function
6. 🟠 `tests/test_cv_fetch_jd.py` — mock KMPAdapter + DB

---

## Acceptance Criteria

- URL → JD.md saved at correct path
- Vacancy row in SQLite with correct site, title, markdown_path, status=fetched
- Duplicate URL → no double insert, informative reply
- kmp error → user-friendly Telegram reply
