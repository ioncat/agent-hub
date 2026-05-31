# agent-hub

Personal multi-agent hub for workflow automation.  
**CV pipeline is the first agent** — more domains planned. The hub orchestrates purpose-built services that were already developed independently; agent-hub connects them into automated pipelines.

> 🚧 Actively in development

---

## User Journey — CV Agent

New jobs are discovered **automatically** via RSS. The agent notifies via Telegram — user only makes decisions.  
Manual URL input is an option, not the default.

```mermaid
flowchart LR
    M["job-board-monitor\nRSS auto-discovery"] -->|"pushes new vacancy"| A
    A["🔔 Telegram\nNew job at X — Analyze?"]
    A -->|✅ Yes| C["Fit analysis\nScore · Verdict · Barriers"]
    C --> D["Telegram\nGenerate CV?"]
    D -->|📄 Yes| E["AI drafts CV\n+ self-review pass"]
    E --> F["User approves\nvia Telegram"]
    F --> G["📎 PDF delivered"]
    G --> H["Telegram\nCover letter?"]
    H -->|✉️ Yes| I["Cover letter\ndelivered"]
    A -->|❌ Skip| Z["Archived"]
    U["Manual option\nTelegram URL / JD.md drop"] -.->|fallback| A
```

**User's only job:** approve or skip. Everything else runs automatically.

---

## AI Pipeline

Five-phase Claude API pipeline. `PROFILE.md` cached — charged once per session window.

```mermaid
flowchart TD
    JD["JD.md"] --> P1["Phase 1 — Deep Analysis\nobjections · hidden requirements · archetype signal"]
    PROF["PROFILE.md\n🔵 prompt cache"] --> P1
    PROF --> P3

    P1 --> P2["Phase 2 — Fit Scoring\nVerdict · Key Barriers · Adaptation Plan · Fit Breakdown"]
    P2 --> QS["Quick Scan → Telegram\nScore / Verdict / Barriers / Warnings"]

    QS -->|"подавать / с адаптацией"| P3["Phase 3 — CV Draft\nhidden from user"]
    P3 --> P35["Phase 3.5 — Self-Review\ncross-checks Adaptation Plan · shown for approval"]
    P35 --> PDF["CV.pdf → Telegram"]
    PDF --> P4["Phase 4 — Cover Letter → Telegram"]
```

**3-way verdict:** подавать · подавать с адаптацией · не подавать  
**Fit Breakdown:** per-requirement ✅/⚠️/❌ table — pet-projects never equal commercial experience  
**Archetype-aware:** JD signals Founder Proxy vs Executor → different CV framing per vacancy

---

## Architecture

```mermaid
flowchart TB
    subgraph Inputs
        RSS["job-board-monitor\nRSS → seen_jobs.json"]
        User["User · Telegram"]
    end

    subgraph "agent-hub"
        TG["Telegram Bot\naiogram 3.x"]
        RT["Router\nPydanticAI Agent"]
        Tools["Tools\ncv_fetch · cv_analyze · cv_generate · cv_cover"]
        LLM["LLM Client\nClaude Sonnet 4.6\nprompt caching + extended thinking"]
        Web["Web Tracker\nFastAPI + HTMX + Jinja2"]
    end

    subgraph "Pipeline Services"
        KMP["knowledge-mirror-parser\nURL → Markdown\nHTTP POST /parse"]
        CBK["callback-cv\nPROFILE.md · prompts · cv_to_pdf\nfilesystem + subprocess"]
    end

    subgraph Storage
        DB[("SQLite\nvacancy metadata · llm_usage")]
        FS["Filesystem\nvacancies/ — JD · analysis · CV · cover"]
    end

    RSS --> RT
    User --> TG --> RT
    RT --> Tools
    Tools --> LLM
    Tools --> KMP
    Tools --> CBK
    Tools --> DB & FS
    Web --> DB
```

| Layer | Tech |
|-------|------|
| AI | Claude Sonnet 4.6 · PydanticAI · prompt caching |
| UI | Telegram (aiogram 3.x) · Web tracker (FastAPI + HTMX) |
| HTTP | httpx async |
| Storage | SQLite + filesystem |
| Config | `config/profile.yaml` · `config/llm.yaml` |
| Deploy | Docker Compose — agent-hub + kmp-service |

---

## Built on existing tools

The agent's value is **orchestration** — it connects three independently built services into a single pipeline. Each service was useful alone; together they enable automation that none could do individually.

| Repo | What it brings | Interface |
|------|----------------|-----------|
| `knowledge-mirror-parser` | URL → clean Markdown — any job board becomes parseable input | HTTP `POST /parse` |
| `callback-cv` | Candidate profile · tailored prompts · PDF generation — the CV engine | Filesystem + subprocess |
| `job-board-monitor` | RSS watcher — turns job boards into a real-time feed | `seen_jobs.json` |

---

## Quick Start

```bash
cp .env.example .env          # ANTHROPIC_API_KEY + TELEGRAM_BOT_TOKEN
docker-compose up -d          # agent-hub + kmp-service
python agent.py               # run without Docker
uvicorn web.api:app --reload  # web tracker → localhost:8080
```
