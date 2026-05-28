# agent-hub — Project Backlog & Design Notes

> Status: pre-development / design phase
> Last updated: 2026-05-28

---

## Vision

A personal AI agent that orchestrates multiple specialized services via tool use.
Starts with CV/job application pipeline. Designed to extend to any personal workflow.

**Core idea:** The agent is a generic orchestrator. Each domain (jobs, YouTube, quotes, etc.) = a set of tools. Adding a new domain = adding new tool definitions, no changes to core.

---

## Architecture

### Components (existing, to be integrated)

| Repo | Role | Status |
|------|------|--------|
| `job-board-monitor` | RSS feed watcher → new job discovery | ✅ Done |
| `knowledge-mirror-parser` | URL → clean Markdown (fetch + html2text) | ✅ Done |
| `callback-cv` | JD analysis → fit score → CV/cover generation | ✅ Done |
| `agent-hub` | Orchestration + user interface + routing | 🔧 This repo |

### Agent core (generic, domain-agnostic)

```
agent-hub/
├── core/
│   ├── telegram.py       — bidirectional Telegram bot (inline keyboards, callbacks)
│   ├── tool_registry.py  — register/discover tools
│   └── router.py         — AI decides which tool(s) to invoke
│
├── tools/
│   ├── cv_fetch_jd.py        — fetch URL → save JD.md to callback-cv inbox
│   ├── cv_analyze.py         — trigger Phase 1+2 analysis
│   ├── cv_generate.py        — generate CV/cover via Claude API
│   ├── cv_get_tracker.py     — read tracker.json → formatted summary
│   ├── yt_transcribe.py      — [BACKLOG] YouTube link → transcription + summary
│   └── quote_store.py        — [BACKLOG] save quote to personal knowledge base
│
├── config/
│   └── profile.yaml      — user-specific settings (see Onboarding task below)
│
└── agent.py              — entry point
```

### Communication between services

| From → To | Method |
|-----------|--------|
| job-board-monitor → agent | POST webhook or poll `seen_jobs.json` |
| agent → knowledge-mirror-parser | direct Python import or HTTP `/parse?url=` |
| agent → callback-cv | filesystem: write to `vacancies/` inbox |
| agent → user | Telegram inline keyboard + callback_query handler |

---

## Full Automated Flow (CV pipeline)

```
RSS feed (DOU/Djinni)
  ↓ job-board-monitor: new vacancy detected {url, title}
  ↓
agent pre-filter (Claude API):
  "Is this PM/PO relevant?" → yes/no + confidence
  → irrelevant: skip silently (or notify user)
  ↓
Telegram → user:
  "🆕 Product Manager at X [7/10 likely fit]
   [✅ Analyze] [❌ Skip]"
  ↓ user taps ✅
  ↓
tool: cv_fetch_jd(url)
  → knowledge-mirror-parser: URL → MD
  → save vacancies/[folder]/JD.md
  ↓
tool: cv_analyze(folder)
  → callback-cv: Phase 1+2 → JD_analysis.md
  ↓
Telegram → user:
  "✅ Analysis done: 8/10 — подавать
   [📄 Generate CV] [📋 Open Tracker] [❌ Skip]"
  ↓ user taps 📄
  ↓
tool: cv_generate(vacancy_id)
  → Claude API with SKILL.md + PROFILE.md context
  → saves [Name]_CV.md + [Name]_CV.pdf
  ↓
Telegram → user:
  "📄 CV ready: Oleksii_Bondarenko_CV.pdf
   [✅ Done] [✏️ Revise]"
```

---

## Open Questions

- [ ] **Agent framework**: Claude API (tool use) vs Hermes vs other? Not decided.
- [ ] **Communication**: direct imports vs HTTP API between services?
- [ ] **Deployment**: local only vs Docker containers?
- [ ] **Telegram polling vs webhook**: long polling simpler for local, webhook better for server.

---

## Backlog

### P0 — Core (CV pipeline, first working end-to-end)

- [ ] `core/telegram.py` — bidirectional bot, inline keyboards, callback_query handler
- [ ] `core/tool_registry.py` — generic tool registration
- [ ] `core/router.py` — Claude API routes user intent to tool
- [ ] `tools/cv_fetch_jd.py` — URL → JD.md in callback-cv inbox
- [ ] `tools/cv_analyze.py` — trigger Phase 1+2
- [ ] `tools/cv_generate.py` — generate CV via Claude API
- [ ] `tools/cv_get_tracker.py` — read tracker.json
- [ ] Integration: job-board-monitor → agent (new job callback)
- [ ] Pre-filter: Claude API screens RSS title for PM/PO relevance before fetching

### P1 — Onboarding (portfolio generalization)

- [ ] `setup.py` / `onboarding.py` — interactive setup:
  - User name (English + Ukrainian variants)
  - Response language preference
  - CV language rules (per vacancy language)
  - Profile input (LinkedIn URL or manual)
  - Auto-generate PROFILE.md + SKILL.md from user input
- [ ] Decouple SKILL.md from hardcoded Russian/Ukrainian rules
- [ ] Make PROFILE.md a template with placeholders

### P2 — Extensions (new domains)

- [ ] `tools/yt_transcribe.py` — YouTube URL → transcript + summary → interesting/not interesting
- [ ] `tools/quote_store.py` — save quote to personal knowledge base (Obsidian / file)
- [ ] `tools/email_draft.py` — draft email on request

### P3 — Polish

- [ ] Docker Compose: all services + agent in containers
- [ ] Public README as portfolio piece
- [ ] Architecture diagram

---

## Design Decisions (recorded)

**2026-05-28:**
- Multi-service architecture preferred over monorepo merge (services stay autonomous)
- Agent core is generic; tools are domain-specific (add YouTube = add one tool file)
- Build generic core + CV tools first; expand later
- Telegram is primary user interface (already exists in job-board-monitor)
- File system (`vacancies/`) serves as event queue between parser and CV pipeline
- Agent framework (Claude/Hermes/other) not decided yet — core should be swappable
