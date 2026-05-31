# agent-hub

**A multi-agent AI operations platform.** Each agent automates one domain end-to-end; the platform orchestrates independent services into workflows. New agents are added over time — this is a growing platform, not a single tool.

### Agent roster

| # | Agent | Domain | Status |
|---|-------|--------|--------|
| 1 | **CV Agent** | Job applications — analyze fit, decide, tailor CV | 🟢 In production |
| 2 | — | *Personal notes, knowledge & content classification and management* | ⚪ Upcoming |

> 🚧 **Actively in development.** The platform is expanding — the CV Agent is the first of many.

---

## The Problem

Job seekers spend hours tailoring CVs **before** knowing if they're even a strong candidate.

Most tools help you write faster. This system answers two questions, in order:

1. **Should you apply?** — an honest read of the vacancy and your real fit. Weak odds → it tells you to skip.
2. **How do you win this one?** — if worth it, a CV that puts your strongest, most relevant sides forward.

The leverage is your profile: prepare it once, and the platform turns deep JD analysis into a winning pitch — automatically.

---

## Product Vision

**Agent Hub is a personal AI operations platform** — a home for domain agents that grows over time (see the [agent roster](#agent-roster) above).

**Core idea:** specialized services remain independent, reusable products. Agent Hub orchestrates them into end-to-end workflows — without absorbing them. Adding a new domain means adding an agent, not rebuilding the platform.

---

## What the CV Agent does

For every incoming vacancy, the agent runs a decision-first pipeline:

- **Deep JD analysis** — goes beyond keywords. Understands the pain the employer is actually trying to solve, surfaces hidden requirements, flags company/role context risks
- **Honest fit verdict** — score, key barriers, archetype match. If the fit is weak → the system says *don't apply* and explains why. No false encouragement, no wasted energy.
- **Tailored CV on demand** — only if worth applying. Generates a CV that maximally surfaces relevant experience for this specific role and reframes it to answer what the JD is really asking for
- **Time saved, not just effort saved** — the pipeline runs automatically. The user only makes go/no-go calls.

---

## User Journey — CV Agent

New jobs are discovered **automatically** via RSS. The agent notifies via Telegram — the user only makes decisions.  
Manual URL input is an option, not the default.

```mermaid
flowchart LR
    M["job-board-monitor\nRSS auto-discovery"] -->|"pushes new vacancy"| A
    A["🔔 Telegram\nNew job at X — Analyze?"]
    A -->|✅ Yes| C["Deep JD Analytics\nScore · Verdict · Barriers"]
    C --> D["Telegram\nGenerate CV?"]
    D -->|📄 Yes| E["AI drafts CV\n+ self-review pass"]
    E --> F["User approves\nvia Telegram"]
    F --> G["📎 PDF delivered"]
    G --> H["Telegram\nCover letter?"]
    H -->|✉️ Yes| I["Cover letter\ndelivered"]
    A -->|❌ Skip| Z["Archived"]
    U["Manual option\nTelegram URL / JD.md drop"] -.->|fallback| A
```

**The user's only job:** approve or skip. Everything else runs automatically.

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

    QS -->|"apply / apply with adaptation"| P3["Phase 3 — CV Draft\nhidden from user"]
    P3 --> P35["Phase 3.5 — Self-Review\ncross-checks Adaptation Plan · shown for approval"]
    P35 --> PDF["CV.pdf → Telegram"]
    PDF --> P4["Phase 4 — Cover Letter → Telegram"]
```

**3-way verdict:** apply · apply with adaptation · don't apply  
**Fit Breakdown:** per-requirement ✅/⚠️/❌ table — pet-projects never equal commercial experience  
**Archetype-aware:** JD signals Founder Proxy vs Executor → different CV framing per vacancy

---

## Product Decisions

| Decision | Alternative | Reason |
|----------|-------------|--------|
| **Decision-first pipeline** — analyze fit before generating anything | Generate CV for every vacancy | Effort should follow a go/no-go verdict, not precede it. Don't optimize a document the user shouldn't send. |
| **RSS-first workflow** — jobs are pushed to the user | Manual vacancy search | Users should *evaluate* opportunities, not spend time *finding* them. |
| **Telegram as primary UI** | Web app / dedicated client | Zero install, already in the user's pocket, native push + inline approve/skip buttons. The interaction is decisions, not browsing. |
| **Independent services** | Single monolith application | Each service stays reusable and independently evolvable. The parser, CV engine, and monitor are products in their own right. |
| **Orchestration over absorption** | Rebuild every capability inside the hub | Reuse existing, battle-tested tools. The hub's value is connecting them, not replacing them. |
| **Human-in-the-loop on irreversible steps** | Full auto-apply | The user owns the apply/skip and CV-approval calls. Automation removes toil, not judgment. |

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

The platform's value is **orchestration** — it connects three independently built services into one pipeline. Each was useful alone; together they enable automation none could do individually.

| Repo | What it brings | Interface |
|------|----------------|-----------|
| `knowledge-mirror-parser` | URL → clean Markdown — any job board becomes parseable input | HTTP `POST /parse` |
| `callback-cv` | Candidate profile · tailored prompts · PDF generation — the CV engine | Filesystem + subprocess |
| `job-board-monitor` | RSS watcher — turns job boards into a real-time feed | `seen_jobs.json` |
