# career-agent — Backlog

> Last updated: 2026-06-01
> Epic format: post-pivot epics (13+) live in `docs/delivery/epics/`. This file = priority tracker + status overview.
> Pre-pivot epics (1–12): `docs/delivery/epics-archive/EPIC-01-12-pre-pivot.md`

---

## P0 — Market Research (do before next dev sprint)

### 🔴 Competitive landscape analysis

**Goal:** Understand the market before building further.

- Find similar services (AI-assisted job search, CV tailoring, fit analysis — PM-focused)
- Critique our strategy and positioning with real market data
- Verdict: is the gap real, what should we adjust?

**How:** Research prompt using `docs/discovery/product-thesis.md` + `docs/discovery/ideas.md` + README. Run against web search.
**Output:** `docs/discovery/competitive-analysis.md`

⚠️ **Reminder** — requested 2026-05-31, still not done.

---

## P0 — Foundation (post-pivot)

| Epic | Title | Status |
|------|-------|--------|
| [EPIC-13](docs/delivery/epics/EPIC-13-multi-user-data-model.md) | Multi-user data model | ✅ Done (2026-06-01) |
| [EPIC-14](docs/delivery/epics/EPIC-14-services-pdf.md) | services/pdf/ — Kill subprocess PDF | ✅ Done (2026-06-01) |
| [EPIC-15](docs/delivery/epics/EPIC-15-services-parser.md) | services/parser/ — Own the parser | ✅ Done (2026-06-01) |
| [EPIC-16](docs/delivery/epics/EPIC-16-services-job-monitor.md) | services/job-monitor/ — Move + redesign | ✅ Done (2026-06-01) |
| [EPIC-17](docs/delivery/epics/EPIC-17-onboarding.md) | Onboarding: PDF → Interview → Profile | ✅ Done Phase 1 (stub interview, 2026-06-01) |
| EPIC-18 | Rename agent-hub → career-agent | ✅ Done (2026-06-01) |
| [EPIC-19](docs/delivery/epics/EPIC-19-local-execution.md) | Local execution mode (web UI) | 📋 Planned |

---

## P1 — Integration

### 🟡 Contract Tests
- [x] `tests/test_parser_adapter.py` — ParserAdapter: mock httpx, test parse/error/health paths
- [ ] `tests/test_cv_adapter.py` — CVAdapter: mock subprocess/httpx, test pdf/error paths (before + after EPIC-14)

### 🟡 End-to-end pipeline verification
- [ ] Run `cv_generate` (Phase 3 + 3.5) on vacancy #47 via e2e_test.py
- [ ] Run `cv_cover` (Phase 4) on vacancy #47
- [ ] Verify: CV.md + PDF artifacts, status transitions, Telegram messages

### 🟡 Multi-skill architecture
**Status: ✅ Phase 1 done (2026-06-01)**
- [x] `prompts/pm/` + `prompts/generic/` — all 5 phases per skill type
- [x] `skill_type` routing in all tools (cv_analyze, cv_generate, cv_cover)
- [x] `AgentDeps.skill_type` — default `'pm'`, seeded from DB user row
- [x] Tested: PM pipeline (SOLAR Digital ✅) + Generic pipeline (AlphaNova ✅)

**Phase 2:**
- [ ] Add `skill_type` question to Telegram `/start` onboarding wizard (→ EPIC-17)

---

## P1 — Pipeline Cost Preview

Feature: cost estimate sent to user before full pipeline run.
Trigger: after `cv_fetch_jd` — JD.md is known, size is known.

```
💰 Оценка бюджета — [Vacancy title]
Phase 1 (анализ):    ~$0.04
Phase 2 (фит):       ~$0.06
Phase 3 (CV draft):  ~$0.05
Phase 3.5 (review):  ~$0.07
Phase 4 (cover):     ~$0.05
──────────────────────────
Итого:               ~$0.27

Запустить полный pipeline? [Да] [Только анализ] [Отмена]
```

- [ ] `tools/cv_estimate.py` — token estimate per phase + cost calc
- [ ] Fallback to baseline averages from `docs/discovery/Tokenomics.md` if no DB history
- [ ] Telegram inline keyboard: [Да] [Только анализ] [Отмена]

---

## P1 — PDF template system

Decision needed: HTML+weasyprint (A), style YAML+fpdf2 (B), or hybrid (C).
See BACKLOG history for option details.

- [ ] Decide approach + document in `docs/discovery/pdf-design-system.md`
- [ ] Prototype one template in chosen format
- [ ] Measure: render time, file size, design flexibility, code reduction

---

## P2 — Onboarding (detail in EPIC-17)

- [ ] See [EPIC-17](docs/delivery/epics/EPIC-17-onboarding.md) for full User Story + tasks

---

## P3 — Infrastructure

- [ ] Telegram webhook mode (config flag, currently long polling)
- [ ] asyncio.Queue → Redis (when concurrent users justify it)

---

## P4 — Extensions

- [ ] `tools/yt_transcribe.py`
- [ ] `tools/quote_store.py`
- [ ] `tools/email_draft.py`
- [ ] Job auto-submit (research feasibility first)

---

## P4.5 — Unit Economics Dashboard

- [ ] `web/api.py` — `GET /api/economics` JSON endpoint
- [ ] `web/templates/economics.html` — Chart.js dashboard:
  - Cost per vacancy (avg + distribution)
  - Phase breakdown (% of total)
  - Cache efficiency (cache_hit_rate, savings in USD)
  - Daily spend (cumulative chart)
  - Unit economics simulator (slider: price/vacancy → margin %)

---

## P5 — Polish & Docs

- [ ] README: Mermaid architecture + pipeline state machine diagrams
- [ ] QUICKSTART.md — one-command startup
- [ ] USER_GUIDE.md — Telegram commands + web tracker
- [ ] Prerequisites doc — external repos layout (post-pivot: irrelevant after EPIC-14/15/16 done)

---

## ✅ Done

### Pre-pivot (EPIC 01–12)
See `docs/delivery/epics-archive/EPIC-01-12-pre-pivot.md`

### Post-pivot
- **EPIC-18** — Rename `agent-hub` → `career-agent` (2026-06-01)
- **EPIC-13** — Multi-user data model: `users` table, `user_id` FK, default user seeding, user-scoped vacancy paths, tracker filter (2026-06-01, 241 tests)
- **EPIC-14** — services/pdf/: render.py + FastAPI /render endpoint, CVAdapter subprocess → httpx (2026-06-01, 235 tests)
- **EPIC-15** — services/parser/: stripped knowledge-mirror-parser, djinni+dou only, docker-compose updated (2026-06-01)
- Multi-skill routing Phase 1 — `prompts/pm/` + `prompts/generic/`, skill_type in AgentDeps (2026-06-01)
- **EPIC-17 Phase 1** — Telegram onboarding: /start FSM, PDF upload (pypdf), profile_json in DB, /update_profile, /set_skill, ClaudeProvider loads from DB, MULTI_USER_ENABLED flag (2026-06-01, 250 tests)
