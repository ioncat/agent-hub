# agent-hub — Backlog

> Last updated: 2026-05-29

---

## P0 — Core (CV pipeline end-to-end)

### 🔴 BLOCKER: knowledge-mirror-parser HTTP endpoint
- [ ] Add FastAPI to knowledge-mirror-parser: `POST /parse` → accepts `{url}` → returns `ParsedDocument` JSON
- [ ] `ParsedDocument`: `{title, markdown, source_url}`
- [ ] Add to Docker Compose as `kmp-service:8001`
- [ ] Blocks: cv_fetch_jd (KMPAdapter call), end-to-end pipeline test

### 🟢 Docker Compose + launch scripts
- [ ] `docker-compose.yml` — finalize: agent-hub + kmp-service, shared vacancies/ volume
- [ ] `scripts/start_tracker.bat` — one-click web tracker launch (sets env vars, opens browser)

---

## P1 — Integration

### 🔴 BLOCKER: kmp site configs (depends: kmp HTTP endpoint)
- [ ] Inspect Djinni job page HTML → `content_selector` + `garbage_selectors`
- [ ] Inspect DOU job page HTML → same
- [ ] Add configs to knowledge-mirror-parser

### 🟡 Contract Tests
- [ ] `tests/test_kmp_adapter.py` — contract test: KMPAdapter interface
- [ ] `tests/test_cv_adapter.py` — contract test: CVAdapter interface
- [ ] `tests/test_web_reader.py` — VacancyView + build_vacancy_view unit tests

### 🟡 End-to-end pipeline test
- [ ] Run full pipeline on a real vacancy URL: fetch → analyze → generate → cover
- [ ] Verify DB state transitions + file artifacts + Telegram messages

---

## P2 — Onboarding

- [ ] **Multi-user onboarding flow** (Telegram-native):
  - User sends `/start` → bot asks: name, target role, RSS feed URLs, uploads CV PDF
  - PDF → Markdown conversion → personalized PROFILE.md generated
  - Follow-up refinement: name variants (EN/UA), what to highlight vs. hide per role type,
    experience framing rules per vacancy archetype
  - Each user gets isolated profile + vacancies folder + separate DB namespace
  - RSS feeds stored per-user, watcher spawned per-user on login
  - **Web tracker becomes multi-user:** per-user auth (Telegram login or token), filtered view by user_id

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

## P5 — Polish & Docs

- [ ] README: Mermaid logical diagram + architecture diagram + state machine diagram
- [ ] QUICKSTART.md — one-command startup guide
- [ ] USER_GUIDE.md — Telegram commands + web tracker usage
- [ ] `scripts/start_tracker.bat` — one-click launch
- [ ] One-command Docker startup

---

## ✅ Done (P0)

- DB: schema.sql + database.py + init + migration (import_tracker.py, 46 vacancies)
- LLM client: ClaudeProvider + prompt caching (PROFILE.md as system prompt)
- Adapters: KMPAdapter (httpx), CVAdapter (subprocess)
- Contracts: ParsedDocument, AnalysisResult, CVResult
- Telegram: aiogram 3.x, long polling, callback_query, inline keyboards
- Router: PydanticAI Agent + tool_registry.py
- Prompts: phase1–phase4 (all 5 files)
- CV Tools: cv_fetch_jd, cv_analyze, cv_generate, cv_cover, cv_get_tracker
- Web tracker: web/api.py + web/templates/tracker.html + web/reader.py
- RSS Watcher: core/rss_watcher.py + scripts/emit_vacancy.py
- File logging: RotatingFileHandler (logs/agent.log, 5MB×5)
- Timing logs: all LLM calls + HTTP fetches
- DB state machine logs: vacancy status transitions + pipeline run transitions
- .env.example, .gitignore
