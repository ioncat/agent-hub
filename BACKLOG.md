# agent-hub — Backlog

> Last updated: 2026-05-29

---

## P0 — Core (CV pipeline end-to-end)

### 🔴 BLOCKER: knowledge-mirror-parser HTTP endpoint
- [ ] Add FastAPI to knowledge-mirror-parser: `POST /parse` → accepts `{url}` → returns `ParsedDocument` JSON
- [ ] `ParsedDocument`: `{title, markdown, source_url}`
- [ ] Add to Docker Compose as `kmp-service:8001`
- [ ] Blocks: cv_fetch_jd.py, KMPAdapter

### 🔴 BLOCKER: Database
- [ ] `db/schema.sql` — SQLite schema (vacancies, status, paths, fit data)
- [ ] DB init + migration script for existing vacancy folders
- [ ] Blocks: all tools, web tracker

### 🔴 BLOCKER: LLM client
- [ ] `core/llm_client.py` — `BaseLLMProvider`, `ClaudeProvider` with prompt caching, `OllamaProvider` stub
- [ ] `config/llm.yaml`
- [ ] Prompt caching: PROFILE.md as cached system prompt (`cache_control: ephemeral`)
- [ ] Blocks: router.py, all analysis tools

### 🟠 Adapters + Contracts (depends: kmp-service HTTP)
- [ ] `contracts/parsed_document.py` — `ParsedDocument(BaseModel)`
- [ ] `contracts/cv_result.py` — `AnalysisResult`, `CVResult`
- [ ] `adapters/kmp_adapter.py` — `KMPAdapter.fetch_markdown(url)` via httpx
- [ ] `adapters/cv_adapter.py` — `CVAdapter.to_pdf(md_path)` via subprocess

### 🟠 Telegram (depends: nothing)
- [ ] `core/telegram.py` — aiogram 3.x, long polling, inline keyboards, `callback_query`
- [ ] Two async tasks in `agent.py`: TelegramPoller + RSSWatcher
- [ ] asyncio.Queue for WorkerPool

### 🟠 Core routing (depends: LLM client, Telegram)
- [ ] `core/tool_registry.py`
- [ ] `core/router.py` — PydanticAI Agent with tool definitions
- [ ] `agent.py` — entry point, event loop startup

### 🟡 Prompts (depends: nothing, can start now)
- [ ] `prompts/phase1_analysis.md` — extract from SKILL.md Phase 1, API-clean
- [ ] `prompts/phase2_fit.md`
- [ ] `prompts/phase3_cv_draft.md`
- [ ] `prompts/phase3_5_review.md`
- [ ] `prompts/phase4_cover.md`

### 🟡 CV Tools (depends: DB, LLM client, adapters, prompts, Telegram)
- [ ] `tools/cv_fetch_jd.py` — KMPAdapter.fetch_markdown → JD.md → SQLite INSERT
- [ ] `tools/cv_analyze.py` — Phase 1+2 → JD_analysis.md + SQLite UPDATE
- [ ] `tools/cv_generate.py` — Phase 3 → Phase 3.5 → approve → CV.md + PDF + SQLite UPDATE
- [ ] `tools/cv_cover.py` — Phase 4 → Telegram message + Cover.md
- [ ] `tools/cv_get_tracker.py` — SQLite → Telegram summary

### 🟡 Web tracker (depends: DB)
- [ ] `web/api.py` — FastAPI: GET /, GET /api/vacancies, GET /api/vacancies/{id}
- [ ] `web/templates/tracker.html` — HTMX + Jinja2

### 🟢 Docker Compose
- [ ] `docker-compose.yml` — agent-hub + kmp-service, shared vacancies/ volume
- [ ] `.env.example`

---

## P1 — Integration

### 🟠 knowledge-mirror-parser site configs (depends: kmp HTTP endpoint)
- [ ] Inspect Djinni job page HTML → `content_selector` + `garbage_selectors`
- [ ] Inspect DOU job page HTML → same
- [ ] Add configs to knowledge-mirror-parser

### 🟡 RSS Integration
- [ ] RSSWatcher: poll `seen_jobs.json` from job-board-monitor
- [ ] Vacancies watcher: detect manual folder drop into vacancies/
- [ ] `config/profile.yaml` — service URLs, Telegram chat IDs, paths

### 🟡 Contract Tests
- [ ] `tests/test_kmp_adapter.py` — contract test: KMPAdapter interface
- [ ] `tests/test_cv_adapter.py` — contract test: CVAdapter interface

---

## P2 — Onboarding

- [ ] Interactive Telegram onboarding: name variants, contacts, profile
- [ ] Auto-generate PROFILE.md per user
- [ ] Decouple SKILL.md language rules
- [ ] **Multi-user onboarding flow** (Telegram-native):
  - User sends `/start` → bot asks: name, target role, RSS feed URLs, uploads CV PDF
  - PDF → Markdown conversion → personalized PROFILE.md generated
  - Follow-up refinement: name variants (EN/UA), what to highlight vs. hide per role type,
    experience framing rules per vacancy archetype (e.g. "emphasize 0→1 for startups, de-emphasize for enterprise")
  - Each user gets isolated profile + vacancies folder + separate DB namespace
  - RSS feeds stored per-user, watcher spawned per-user on login

---

## P3 — Microservices expansion

- [ ] callback-cv: add FastAPI endpoint (`POST /analyze`, `POST /pdf`)
- [ ] CVAdapter switches from subprocess to HTTP (no changes in tools layer)
- [ ] Telegram webhook (config flag)
- [ ] asyncio.Queue → Redis

---

## P4 — Extensions

- [ ] `tools/yt_transcribe.py`
- [ ] `tools/quote_store.py`
- [ ] `tools/email_draft.py`
- [ ] Job auto-submit (research feasibility)

---

## P5 — Polish

- [ ] Public README with architecture narrative
- [ ] Mermaid architecture diagram
- [ ] One-command startup
