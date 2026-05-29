# agent-hub — Product Backlog

Navigation and overview of all epics, organized by development phase.

---

## Phase 1: Core Infrastructure 🔧

Foundational layer: async runtime, storage, LLM client, Telegram bot, agent routing.
All Phase 2 work depends on this phase being complete.

### Epic 1: knowledge-mirror-parser HTTP Endpoint
**Description**: Add FastAPI `POST /parse` to kmp — accepts URL, returns `ParsedDocument` JSON. Site configs for Djinni + DOU. Dockerfile + docker-compose entry. Defines the service contract used by agent-hub's KMPAdapter.  
**Status**: 🟢 Done | **Priority**: 🔴 P0  
[View Epic →](./epics/EPIC-1.md)

### Epic 2: Database Layer
**Description**: SQLite schema for vacancy metadata and pipeline status. Migration script for existing vacancy folders. Replaces `tracker.json`.  
**Status**: 🟢 Done | **Priority**: 🔴 P0  
[View Epic →](./epics/EPIC-2.md)

### Epic 3: LLM Client
**Description**: PydanticAI-based `LLMClient` with `ClaudeProvider` (prompt caching via `cache_control: ephemeral`) and `OllamaProvider` stub.  
**Status**: 🟢 Done | **Priority**: 🔴 P0  
[View Epic →](./epics/EPIC-3.md)

### Epic 4: Telegram Bot
**Description**: aiogram 3.x long polling, chat_id security filter, text→router dispatch, send helpers, inline keyboards.  
**Status**: 🟢 Done | **Priority**: 🔴 P0  
[View Epic →](./epics/EPIC-4.md)

### Epic 5: Core Agent Routing
**Description**: `tool_registry.py`, `router.py` (PydanticAI Agent), `agent.py` entry point. Routes user intent to registered tools.  
**Status**: 🟢 Done | **Priority**: 🔴 P0  
[View Epic →](./epics/EPIC-5.md)

---

## Phase 2: CV Pipeline 📄

End-to-end CV application workflow: fetch JD → analyze → generate CV → cover message.
Depends on Phase 1 complete.

### Epic 6: Prompt Files
**Description**: API-clean prompt files extracted from `callback-cv/skill/SKILL.md` — one file per phase (1 analysis, 2 fit, 3 CV draft, 3.5 self-review, 4 cover). No Claude Code artifacts.  
**Status**: 🔵 Planned | **Priority**: 🟠 P1  
[View Epic →](./epics/EPIC-6.md)

### Epic 7: CV Fetch JD Tool
**Description**: `tools/cv_fetch_jd.py` — fetch vacancy URL via knowledge-mirror-parser (async), save `JD.md`, register vacancy in SQLite.  
**Status**: 🔵 Planned | **Priority**: 🟡 P2  
[View Epic →](./epics/EPIC-7.md)

### Epic 8: CV Analysis Tool
**Description**: `tools/cv_analyze.py` — Phase 1+2: JD + prompts + cached PROFILE → Claude API → `JD_analysis.md`. Telegram message: Quick Scan block.  
**Status**: 🔵 Planned | **Priority**: 🟡 P2  
[View Epic →](./epics/EPIC-8.md)

### Epic 9: CV Generation Tool
**Description**: `tools/cv_generate.py` — Phase 3 draft (hidden) → Phase 3.5 self-review → Telegram approval → `[Name]_CV.md` + `[Name]_CV.pdf`.  
**Status**: 🔵 Planned | **Priority**: 🟡 P2  
[View Epic →](./epics/EPIC-9.md)

### Epic 10: Cover Message Tool
**Description**: `tools/cv_cover.py` — Phase 4: cover message → Telegram text message + `[Name]_Cover.md`.  
**Status**: 🔵 Planned | **Priority**: 🟡 P2  
[View Epic →](./epics/EPIC-10.md)

### Epic 11: Tracker Tool
**Description**: `tools/cv_get_tracker.py` — SQLite query → formatted Telegram summary (top N vacancies, status, fit scores).  
**Status**: 🔵 Planned | **Priority**: 🟡 P2  
[View Epic →](./epics/EPIC-11.md)

### Epic 12: Web Tracker
**Description**: `web/api.py` FastAPI + HTMX + Jinja2 tracker. Replaces static `tracker.html`. Endpoints: `GET /`, `GET /api/vacancies`, `GET /api/vacancies/{id}`.  
**Status**: 🔵 Planned | **Priority**: 🟡 P2  
[View Epic →](./epics/EPIC-12.md)

---

## Phase 3: Integration 🔗

Connect agent-hub to external services and RSS feeds.
Depends on Phase 2 CV tools working.

### Epic 13: knowledge-mirror-parser Site Configs
**Description**: Add Djinni and DOU site configurations to knowledge-mirror-parser (`content_selector`, `garbage_selectors`). Requires HTML inspection of job pages.  
**Status**: 🔵 Planned | **Priority**: 🟠 P1  
[View Epic →](./epics/EPIC-13.md)

### Epic 14: RSS Integration
**Description**: `RSSWatcher` polls `seen_jobs.json` from job-board-monitor. Detects new vacancies → notifies user via Telegram. Manual folder-drop path for LinkedIn.  
**Status**: 🔵 Planned | **Priority**: 🟡 P2  
[View Epic →](./epics/EPIC-14.md)

---

## Phase 4: Onboarding 🧑‍💼

Generalize the system for any user (not just Oleksii Bondarenko).

### Epic 15: User Onboarding
**Description**: Interactive Telegram setup: name variants, contacts, profile input, auto-generate `PROFILE.md`. Decouple `SKILL.md` language rules.  
**Status**: 🔵 Planned | **Priority**: 🟡 P2  
[View Epic →](./epics/EPIC-15.md)

---

## Phase 5: Microservices 🐳

Move from single-container imports to proper Docker Compose multi-service architecture.

### Epic 16: Docker Compose Setup
**Description**: Separate containers for agent-hub, knowledge-mirror-parser (FastAPI endpoint), callback-cv. Shared `vacancies/` volume. Webhook switch for Telegram.  
**Status**: 🔵 Planned | **Priority**: 🟢 P3  
[View Epic →](./epics/EPIC-16.md)

---

## Phase 6: Extensions 🌐

New tool domains beyond CV pipeline.

| Epic | Description | Status | Priority |
|------|-------------|--------|----------|
| Epic 17: YouTube Tool | YouTube URL → transcript + summary → Telegram | 🔵 Planned | 🟢 P3 |
| Epic 18: Quote Store | Save quote to knowledge base (Obsidian / file) | 🔵 Planned | 🟢 P3 |
| Epic 19: Email Draft | Draft email on request | 🔵 Planned | 🟢 P3 |
| Epic 20: Job Auto-Submit | Djinni apply automation (research feasibility first) | 🔵 Planned | 🟢 P3 |

---

## UX Polish & Bug Fixes (не эпики)

Небольшие улучшения, не тянущие на отдельный эпик.

| Дата | Описание |
|------|----------|
| — | — |

---

## Summary Statistics

| Phase | Epics | Status |
|-------|-------|--------|
| Phase 1 — Core Infrastructure | 1–5 | 🔵 Planned |
| Phase 2 — CV Pipeline | 6–12 | 🔵 Planned |
| Phase 3 — Integration | 13–14 | 🔵 Planned |
| Phase 4 — Onboarding | 15 | 🔵 Planned |
| Phase 5 — Microservices | 16 | 🔵 Planned |
| Phase 6 — Extensions | 17–20 | 🔵 Planned |

---

## Document Control

- **Version**: 1.0
- **Last Updated**: 2026-05-29
- **Status**: 🔵 Pre-development
