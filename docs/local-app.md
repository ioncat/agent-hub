# Local App — Architecture

**What:** Desktop-mode pipeline runner. No Telegram required. Browser UI → full CV pipeline.
**Who:** Power user / developer / admin. Single-user, local only.
**Entry point:** `uvicorn web.api:app --reload` → `http://localhost:8080`

---

## Request flow

```mermaid
sequenceDiagram
    actor User as 👤 Browser
    participant API as web/api.py<br/>(FastAPI)
    participant Agent as core/router.py<br/>(PydanticAI Agent)
    participant Parser as services/parser<br/>:8001
    participant Claude as Claude API
    participant PDF as services/pdf<br/>:8002
    participant DB as SQLite DB
    participant FS as vacancies/<br/>[user_id]/[site]/[month]/

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

---

## Component map

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

---

## Profile loading (transition)

| Stage | Source |
|-------|--------|
| Pre-EPIC-17 | `skill/users/[id]/PROFILE.md` — filesystem |
| Post-EPIC-17 | DB `users.profile_md` — written during onboarding |
| Transition | `AgentDeps` checks DB first → falls back to file |

---

## Related

- Epic: [`docs/delivery/Epics/EPIC-19-local-execution.md`](delivery/Epics/EPIC-19-local-execution.md)
- Onboarding (profile source): [`docs/delivery/Epics/EPIC-17-onboarding.md`](delivery/Epics/EPIC-17-onboarding.md)
