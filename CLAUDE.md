# Claude Code Guidelines — agent-hub

**Project:** Personal AI agent orchestrator
**Version:** 1.1 (2026-05-29)
**Status:** Pre-development / Design phase

---

## Project Overview

**What:** Generic AI agent orchestrating multiple specialized services via tool use, with Telegram as primary UI.

**Why:** Unified personal workflow automation — CV/job pipeline first, extensible to any domain.

**Current Goal:** Build working CV pipeline end-to-end (P0 backlog complete).

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python |
| **AI** | Claude API via PydanticAI (tool use, prompt caching) |
| **UI** | Telegram bot — aiogram 3.x (long polling, inline keyboards) |
| **Web** | FastAPI + HTMX + Jinja2 |
| **HTTP client** | httpx (async, calls kmp-service and future HTTP services) |
| **Storage** | SQLite (metadata) + filesystem (documents) |
| **Async** | asyncio, no blocking I/O on event loop |
| **Config** | YAML (`config/profile.yaml`, `config/llm.yaml`) |

---

## Project Structure

```
agent-hub/
├── core/
│   ├── telegram.py           — aiogram 3.x, long polling, callback_query
│   ├── tool_registry.py      — generic tool registration
│   ├── router.py             — PydanticAI Agent, routes intent → tool
│   └── llm_client.py         — ClaudeProvider (primary) + OllamaProvider (stub)
├── adapters/
│   ├── kmp_adapter.py        — KMPAdapter: httpx → kmp-service HTTP
│   └── cv_adapter.py         — CVAdapter: filesystem + subprocess
├── contracts/
│   ├── parsed_document.py    — ParsedDocument(BaseModel)
│   └── cv_result.py          — AnalysisResult, CVResult
├── tools/
│   ├── cv_fetch_jd.py        — URL → JD.md → SQLite
│   ├── cv_analyze.py         — Phase 1+2 → JD_analysis.md
│   ├── cv_generate.py        — Phase 3+3.5 → [Name]_CV.pdf
│   ├── cv_cover.py           — Phase 4 → Telegram message
│   └── cv_get_tracker.py     — SQLite → Telegram summary
├── prompts/
│   ├── phase1_analysis.md
│   ├── phase2_fit.md
│   ├── phase3_cv_draft.md
│   ├── phase3_5_review.md
│   └── phase4_cover.md
├── web/
│   ├── api.py            — FastAPI endpoints
│   └── templates/
│       └── tracker.html  — HTMX + Jinja2
├── db/
│   └── schema.sql
├── config/
│   ├── profile.yaml      — paths, Telegram chat IDs
│   └── llm.yaml          — LLM provider config
├── agent.py              — entry point
├── ARCHITECTURE.md       — full design decisions and data flows
├── BACKLOG.md            — prioritized task list
└── CLAUDE.md
```

### Related services (external repos)

| Repo | Role | Interface |
|------|------|-----------|
| `job-board-monitor` | RSS watcher → new jobs | `seen_jobs.json` |
| `knowledge-mirror-parser` | URL → Markdown (must use aiohttp) | Python import |
| `callback-cv` | Analysis prompts, PROFILE.md, cv_to_pdf | Filesystem + subprocess |

---

## Session Memory (MANDATORY)

**Location:** `.claude/sessions/` — gitignored, travels with project.

### On Session Start
1. Read `.claude/sessions/` — check latest session log
2. Check open questions in ARCHITECTURE.md
3. Continue from where previous session left off

⚠️ **If `.claude/sessions/` does not exist:** notify user, create after confirmation.

### On Session End
Create `.claude/sessions/YYYY-MM-DD-short-description.md`:

```markdown
# Session: YYYY-MM-DD — Short Title

## Done
## Decisions
## Next
## Commits
```

---

## Project Memory

**Location:** `.claude/memory/` — gitignored, travels with project.

---

## Global Rules

See `E:\My files\0 My_Dev\my_prj\my_claude\INTERACTION_RULES.md`:
- Rule 0: Communicate in Russian or English
- Rule 1: Wait for answers before acting
- Rule 2: Self-explaining UI
- Rule 3: Session/memory in `.claude/` inside project
- Rule 4: Commit messages in English (conventional commits)
- Rule 5: Task lists ordered by blockers (🔴/🟠/🟡/🟢)

---

## Common Commands

| Command | Purpose |
|---------|---------|
| `python agent.py` | Start agent |
| `python -m pytest` | Run tests |
| `uvicorn web.api:app --reload` | Start web tracker |

---

## Critical Rules

- **Never hardcode** user data — use `config/profile.yaml` and `callback-cv/skill/PROFILE.md`
- **No blocking I/O** on asyncio event loop — use httpx/asyncio.sleep only
- **Adapter layer is mandatory** — never import external service internals directly. All calls go through `adapters/`
- **Contracts are typed** — adapters return Pydantic BaseModel objects from `contracts/`, never raw dicts or service objects
- **Agent framework swappable** — `router.py` receives `LLMClient` via DI
- **Tools are domain-specific** — new domain = new tool file, no core changes
- **Telegram is primary UI** — all user-facing output goes through bot
- **Prompt caching mandatory** — PROFILE.md always as cached system prompt in ClaudeProvider
- **No silent LLM degradation** — if Claude unavailable, notify user and raise; never silently use local LLM
- **Phase 3 → 3.5 sequence** — CV draft always goes through self-review before showing to user
- **HTTP from day 1** — knowledge-mirror-parser is a separate service called via HTTP, not imported

---

**Last updated:** 2026-05-29
