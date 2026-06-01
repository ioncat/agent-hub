# Local App — Architecture

**What:** Desktop-mode pipeline runner. No Telegram required. Browser UI → full CV pipeline.
**Who:** Power user / developer / admin. Single-user, local only.
**Entry point:** `uvicorn web.api:app --reload` → `http://localhost:8080`

---

## Request flow (sequence)

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

## Pipeline flow

```mermaid
flowchart TD
    User(["👤 Browser\nPOST /analyze\n{url, user_id}"])
    User --> API["web/api.py\nget user + skill_type from DB"]

    API --> P1

    subgraph P1["⬜ Phase 1 — Fetch JD"]
        direction LR
        F1["cv_fetch_jd"] -->|"POST /parse {url}"| Parser["services/parser\n:8001"]
        Parser -->|"markdown + title"| F1
        F1 --> A1[/"JD.md\nDB: status=fetched"/]
    end

    P1 --> P2

    subgraph P2["⬜ Phase 2 — Analyze"]
        direction LR
        F2["cv_analyze"] -->|"phase1+2 prompt\n+ JD.md + PROFILE"| Claude1["Claude API"]
        Claude1 -->|"fit score\nstrengths / gaps"| F2
        F2 --> A2[/"JD_analysis.md\nDB: status=analyzed"/]
    end

    P2 --> P3

    subgraph P3["⬜ Phase 3 — Generate CV"]
        direction LR
        F3a["cv_generate"] -->|"phase3 prompt\n+ PROFILE + analysis"| Claude2["Claude API"]
        Claude2 -->|CV draft| F3a
        F3a -->|"phase3_5 self-review"| Claude3["Claude API"]
        Claude3 -->|CV reviewed| F3a
        F3a -->|"POST /render {markdown}"| PDF["services/pdf\n:8002"]
        PDF -->|PDF bytes| F3a
        F3a --> A3[/"CV.md + CV.pdf\nDB: status=cv_ready"/]
    end

    P3 --> P4

    subgraph P4["⬜ Phase 4 — Cover Letter"]
        direction LR
        F4["cv_cover"] -->|"phase4 prompt\n+ JD + CV"| Claude4["Claude API"]
        Claude4 -->|cover letter| F4
        F4 --> A4[/"Cover.md\nDB: status=done"/]
    end

    P4 --> Done["✅ {vacancy_id, status: done}"]

    Done -->|"SSE stream\n/pipeline/status/{id}"| SSE(["👤 Browser\nphase progress events"])
    Done -->|"GET /download/{id}/cv.pdf"| DL1(["👤 Browser\nCV.pdf"])
    Done -->|"GET /download/{id}/cover.md"| DL2(["👤 Browser\nCover.md"])
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
