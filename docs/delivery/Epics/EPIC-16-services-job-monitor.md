# EPIC-16 — services/job-monitor/ — Move + redesign job monitor

**Status:** ✅ Done (2026-06-01)
**Phase:** Phase 4 of PIVOT-PLAN
**Priority:** P0 — Foundation
**Last updated:** 2026-06-01

---

## User Story

```
As a job seeker
I want new matching vacancies to appear in my pipeline automatically
So that I don't have to manually submit URLs — the system discovers and queues them for me
```

---

## Acceptance Criteria

**Step 1 — Move (no functional change):**

**Given** `docker compose up`
**When** all services start
**Then** `job-monitor` service builds from `./services/job-monitor/` — no reference to external repo

**Given** job-board-monitor detects a new vacancy
**When** it processes the entry
**Then** career-agent receives it via `POST /api/new-vacancy` (not via `seen_jobs.json` file polling)

**Step 2 — Webhook redesign:**

**Given** `job-monitor` detects a new RSS entry
**When** it hasn't been seen before
**Then** it calls `POST /api/new-vacancy` on career-agent with vacancy URL + metadata

**Given** `POST /api/new-vacancy` is received
**When** the endpoint handler runs
**Then** `cv_fetch_jd` is triggered for the vacancy and user is notified via Telegram

---

## Edge Cases

- career-agent is down when job-monitor tries to push → job-monitor retries with backoff (existing retry logic)
- Duplicate URL pushed twice → `insert_vacancy` raises IntegrityError → endpoint returns 409, job-monitor skips
- `seen_jobs.json` file missing on first run → job-monitor creates it (existing behaviour)

---

## Out of Scope

- Per-user RSS feed subscription — Phase 5 (Onboarding)
- Job-monitor UI / admin panel

---

## Notes for Engineering

- Step 1: move source, no logic change — lowest risk, own PR
- Step 2: replace `send_telegram()` in `monitor.py` → `httpx.post(CAREER_AGENT_URL + "/api/new-vacancy", ...)`
- `web/api.py`: add `POST /api/new-vacancy` endpoint
- `core/rss_watcher.py`: keep startup seed logic (reads existing `seen_jobs.json` on boot), remove polling loop

---

## Dependencies

- Step 1: independent
- Step 2: depends on EPIC-13 (user_id needed for new vacancy routing)

---

## Tasks

| # | Task | Status |
|---|------|--------|
| 1 | Move `monitor.py` + `feeds.json.example` → `services/job-monitor/` | ✅ Done |
| 2 | `services/job-monitor/requirements.txt` + `Dockerfile` | ✅ Done |
| 3 | `docker-compose.yml` — add `job-monitor` container | ✅ Done |
| 4 | `monitor.py` — replace `send_telegram()` → `POST /api/new-vacancy` | ✅ Done |
| 5 | `web/api.py` — `POST /api/new-vacancy` endpoint | ✅ Done |
| 6 | `core/rss_watcher.py` — remove file-polling loop | ✅ Done |
