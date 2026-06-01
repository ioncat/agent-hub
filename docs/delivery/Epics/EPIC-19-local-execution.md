# EPIC-19 — Local execution mode (desktop / local web app)

**Status:** 📋 Planned
**Phase:** Phase 7 of PIVOT-PLAN
**Priority:** P1
**Last updated:** 2026-06-01

---

## User Story

```
As a power user or developer
I want to run the full CV pipeline from a local web UI without Telegram
So that I can use Career Agent as a desktop tool — faster iteration, no bot latency, no phone required
```

---

## Acceptance Criteria

**Given** the user opens the local web UI
**When** they paste or drop a JD URL or text
**Then** the pipeline starts and phase progress is shown in real time (SSE stream)

**Given** the pipeline completes
**When** all phases are done
**Then** CV PDF and cover letter are available for download directly from the browser

**Given** `LOCAL_MODE=true` in settings
**When** the `skill/` pipeline runs via Claude Code slash commands
**Then** artifacts are written to `vacancies/[user_id]/` and the local API is used instead of Telegram

**Given** EPIC-17 (Onboarding) is complete
**When** the local app loads the profile
**Then** it reads from DB — not from `PROFILE.md` file

---

## Edge Cases

- No DB profile yet (pre-EPIC-17) → local app falls back to `skill/users/[id]/PROFILE.md`
- Pipeline fails mid-run → UI shows error state per phase; partial artifacts still downloadable
- Two browser tabs run pipeline simultaneously → each gets independent SSE stream; no cross-contamination

---

## Out of Scope

- Auth / login for local app (single-user, local only)
- Mobile / PWA (separate phase)
- Packaged binary (PyInstaller) — overkill for personal tool

---

## Notes for Engineering

- Extend existing `web/api.py` + `web/templates/` — not a new app
- New endpoint: `POST /analyze` — accepts JD URL or text, triggers pipeline for active user
- New endpoint: `GET /pipeline/status/{vacancy_id}` — SSE stream of phase progress events
- New template: `web/templates/local_app.html` — HTMX: JD drop zone, user selector, phase progress, download links
- `skill/` bridge: `LOCAL_MODE=true` env var → write to `vacancies/[user_id]/`, call local endpoints
- Profile convergence: pre-EPIC-17 uses filesystem PROFILE.md; post-EPIC-17 uses DB — no breaking change during transition

---

## Dependencies

- EPIC-13 (user_id) — required
- EPIC-17 (DB profiles) — partial dependency; local app works before EPIC-17 with file fallback

---

## Architecture

### Request flow

```mermaid
sequenceDiagram
    actor User as 👤 Browser
    participant API as web/api.py<br/>(FastAPI)
    participant Agent as core/router.py<br/>(PydanticAI Agent)
    participant Parser as services/parser<br/>:8001
    participant Claude as Claude API
    participant PDF as services/pdf<br/>:8002
    participant DB as SQLite DB
    participant FS as vacancies/<br/>[user_id]/

    User->>API: POST /analyze {url or text, user_id}
    API->>DB: get user + skill_type
    API->>Agent: run pipeline (AgentDeps)

    Note over Agent: Phase 1 — fetch_jd
    Agent->>Parser: POST /parse {url}
    Parser-->>Agent: {markdown, title}
    Agent->>FS: write JD.md
    Agent->>DB: insert_vacancy (status=fetched)

    Note over Agent: Phase 2 — analyze
    Agent->>Claude: prompts/[skill_type]/phase1+2.md + JD.md
    Claude-->>Agent: JD_analysis.md
    Agent->>FS: write JD_analysis.md
    Agent->>DB: update status=analyzed

    Note over Agent: Phase 3 — generate CV
    Agent->>Claude: prompts/[skill_type]/phase3.md + PROFILE
    Claude-->>Agent: CV.md (draft)
    Agent->>Claude: phase3_5 self-review
    Claude-->>Agent: CV.md (reviewed)
    Agent->>PDF: POST /render {markdown}
    PDF-->>Agent: PDF bytes
    Agent->>FS: write CV.md + CV.pdf
    Agent->>DB: update status=cv_ready

    Note over Agent: Phase 4 — cover letter
    Agent->>Claude: prompts/[skill_type]/phase4.md
    Claude-->>Agent: Cover.md
    Agent->>FS: write Cover.md
    Agent->>DB: update status=done

    API-->>User: {vacancy_id, status: "done"}

    User->>API: GET /pipeline/status/{vacancy_id} (SSE)
    API-->>User: event: phase_done (per phase, streamed)

    User->>API: GET /download/{vacancy_id}/cv.pdf
    API-->>User: CV.pdf (binary)
    User->>API: GET /download/{vacancy_id}/cover.md
    API-->>User: Cover.md (text)
```

### Component map

```mermaid
graph TD
    Browser["👤 Browser<br/>(local_app.html)"]
    API["web/api.py<br/>FastAPI :8080"]
    Agent["core/router.py<br/>PydanticAI Agent"]
    Profile["Profile source"]
    Parser["services/parser<br/>kmp-service :8001"]
    PDF["services/pdf<br/>pdf-service :8002"]
    Claude["Claude API"]
    DB[("SQLite DB<br/>db/agent.db")]
    FS["vacancies/<br/>[user_id]/[site]/[month]/"]

    Browser -->|POST /analyze| API
    Browser -->|SSE /pipeline/status/id| API
    Browser -->|GET /download/id/file| API

    API --> Agent
    Agent --> Profile
    Agent --> Parser
    Agent --> PDF
    Agent --> Claude
    Agent --> DB
    Agent --> FS

    Profile -->|pre-EPIC-17| SKILL["skill/users/[id]/<br/>PROFILE.md"]
    Profile -->|post-EPIC-17| DB
```

### Profile loading (transition)

| Stage | Profile source |
|-------|---------------|
| Pre-EPIC-17 | `skill/users/[id]/PROFILE.md` — read from filesystem |
| Post-EPIC-17 | DB `users.profile_md` — written during onboarding |
| Transition | `AgentDeps` checks DB first → falls back to file |

---

## Tasks

| # | Task | Status |
|---|------|--------|
| 1 | `web/api.py` — `POST /analyze` endpoint | 📋 |
| 2 | `web/api.py` — `GET /pipeline/status/{vacancy_id}` SSE | 📋 |
| 3 | `web/templates/local_app.html` — JD drop zone + phase progress + download | 📋 |
| 4 | `skill/` bridge mode (`LOCAL_MODE=true`) | 📋 |
| 5 | Post-EPIC-17: local app reads profile from DB | 📋 |
