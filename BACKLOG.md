# agent-hub — Backlog

> Last updated: 2026-05-31
> ⚠️ Major pivot 2026-05-31: product is now a focused vertical service for PdM/PO/PM job search.
> Monorepo consolidation, onboarding redesign, multi-user data model added as top priorities.
> See ARCHITECTURE.md → Design Decisions Log → 2026-05-31 for full context.

---

## P0 — Foundation (post-pivot)

### 🔴 Monorepo consolidation — service audit + migration

Before copying anything in: **audit each service first** — strip dead code, cut unused features, make it an organic component of this system.

- [ ] **`services/parser/`** — audit `knowledge-mirror-parser`: what does it actually use? What can be removed? Report findings, then migrate only what's needed. Keep HTTP contract (`POST /parse`), KMPAdapter unchanged.
- [ ] **`services/pdf/`** — extract `cv_to_pdf.py` from callback-cv into a proper FastAPI service (`POST /render`). CVAdapter switches from subprocess → HTTP. No changes in tools layer.
- [ ] **`services/job-monitor/`** — redesign `job-board-monitor` from file-polling → webhook push (`POST /api/new-vacancy`). RSSWatcher becomes a webhook receiver endpoint.
- [ ] Remove callback-cv filesystem dependency from settings. Profile is built by onboarding, not hand-edited.
- [ ] Update `docker-compose.yml` — all services from `services/` subdirectories.

### 🔴 Multi-user data model

Design now — infrastructure incrementally.

- [ ] Add `users` table to `db/schema.sql` — `id`, `telegram_chat_id`, `name`, `created_at`
- [ ] Add `user_id` FK to `vacancies`, `llm_usage`, `pipeline_runs`
- [ ] `database.py` — all queries scoped by `user_id`
- [ ] `AgentDeps` — carries `user_id`, passed to all tools
- [ ] `Settings` — remove single-user `TELEGRAM_CHAT_ID` assumption (keep as default user for now)

### 🔴 Onboarding — PDF → Interview → Profile

- [ ] **PDF → Markdown**: accept `Profile.pdf` via Telegram, convert to Markdown
- [ ] **Profile analysis**: LLM reads candidate profile, builds personalized PM-domain interview (Delivery/Discovery framing, archetype, key projects, gaps)
- [ ] **Conversational interview**: multi-turn Telegram conversation, LLM extracts full depth of experience
- [ ] **Profile generation**: interview transcript → structured profile stored in SQLite per user
- [ ] **Multi-pass**: allow re-interview / profile enrichment at any time

### 🟡 Project rename

- [ ] Decide new name — product is a focused PM job-search service, not a generic "hub"
- [ ] Rename repo, update all references
- [ ] *(Non-blocking — discuss separately)*

---

## P1 — Integration

### 🟡 Contract Tests
- [ ] `tests/test_kmp_adapter.py` — KMPAdapter: mock httpx, test parse/error/health paths
- [ ] `tests/test_cv_adapter.py` — CVAdapter: mock subprocess, test pdf/error paths

### 🟡 End-to-end pipeline — generate + cover phases
- [ ] Run `cv_generate` (Phase 3 + 3.5) on vacancy #47 via e2e_test.py
- [ ] Run `cv_cover` (Phase 4) on vacancy #47
- [ ] Verify: CV.md + PDF artifacts, status transitions, Telegram messages

---

## P1 — Pipeline Cost Preview (pre-run estimate)

**Feature:** Before starting full pipeline processing, agent sends user an estimated cost breakdown.

**Trigger:** after `cv_fetch_jd` completes — JD.md is on disk, size is known.

**How it works:**
- Estimate input tokens per phase using JD size + known PROFILE.md size + prompt sizes (all static)
- Use historical average output tokens per phase from `llm_usage` DB (`AVG(output_tokens) GROUP BY phase`)
- Calculate estimated total cost across all phases using `_calc_cost()`
- Send Telegram message before any LLM calls:

```
💰 Оценка бюджета — [Vacancy title]
JD: ~N tokens

Phase 1 (анализ):    ~$0.04
Phase 2 (фит):       ~$0.06
Phase 3 (CV draft):  ~$0.05
Phase 3.5 (review):  ~$0.07
Phase 4 (cover):     ~$0.05
─────────────────────
Итого:               ~$0.27

Запустить полный pipeline? [Да] [Только анализ] [Отмена]
```

**Implementation notes:**
- Phase 1/2 estimate: `(profile_tokens + prompt_tokens + jd_tokens) × input_price + avg_output × output_price`
- Phase 3/3.5/4 estimate: `(profile_tokens + prompt_tokens + jd_tokens + avg_analysis_output) × price + avg_output × output_price`
- Fallback if no historical data: use hardcoded baseline averages from `docs/discovery/Tokenomics.md`
- Cache savings included: Phase 2–4 use cache_read price for PROFILE.md tokens
- Thinking tokens: included for Phase 1+2 (avg thinking from DB or budget_tokens × 0.35 as estimate)
- New helper: `tools/cv_estimate.py` or inline in `cv_fetch_jd.py` post-fetch

**Why useful:**
- User sees cost before committing to full run
- Enables selective runs ("только анализ" without generate+cover)
- Foundation for budget alerts ("это дороже обычного — JD очень длинный")

---

## P2 — Onboarding

- [ ] **Multi-user onboarding flow** (Telegram-native):
  - User sends `/start` → bot asks: name, target role, RSS feed URLs, uploads CV PDF
  - PDF → Markdown conversion → personalized PROFILE.md generated
  - Follow-up refinement: name variants (EN/UA), what to highlight vs. hide per role type,
    experience framing rules per vacancy archetype
  - **Onboarding fields (profile schema):**
    - `archetype_preference`: `execution` | `founder` | `dual` — drives Phase 2 adaptation advice
    - `archetype_execution_highlights`: which roles/projects to surface for execution JDs
    - `archetype_founder_highlights`: which roles/projects to surface for 0→1/founder JDs
    - `honest_gaps`: list of things never to fabricate (no-code tools, A/B testing, etc.)
    - `name_variants`: EN formal/informal + native language variants
    - `target_roles`: list of role types candidate is targeting
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

## P4.5 — Unit Economics Dashboard

**Context:** agent-hub как CV-processing сервис. Данные из таблицы `llm_usage`.

- [ ] `web/api.py`: новый endpoint `GET /economics`
- [ ] `web/templates/economics.html` — дашборд с расчётами и графиками:
  - **Cost per vacancy** — среднее и распределение по вакансиям
  - **Phase breakdown** — сколько стоит phase1/2/3/3.5/4 в среднем и % от total
  - **Cache efficiency** — cache_hit_rate (cache_read / total_input), экономия в USD
  - **Daily spend** — накопительный graf расходов по дням
  - **Unit economics симулятор** — слайдер: "если брать $X/вакансия → margin Y%"
  - **Gross margin** при разных моделях монетизации ($0.99, $4.99, $9.99/вакансия)
- [ ] Графики через Chart.js CDN (как marked.js — без build step)
- [ ] Данные через `GET /api/economics` JSON endpoint → Chart.js рендерит

**Ключевые SQL запросы:**
```sql
SELECT phase, COUNT(*), AVG(cost_usd), SUM(cost_usd) FROM llm_usage GROUP BY phase;
SELECT DATE(created_at), SUM(cost_usd) FROM llm_usage GROUP BY DATE(created_at);
SELECT SUM(cache_read_tokens)*1.0/(SUM(input_tokens)+SUM(cache_read_tokens)) AS cache_hit_rate FROM llm_usage;
SELECT v.id, v.title, SUM(u.cost_usd) AS cost FROM llm_usage u JOIN vacancies v ON u.vacancy_id=v.id GROUP BY v.id;
```

---

## P5 — Polish & Docs

- [ ] README: Mermaid logical diagram + architecture diagram + state machine diagram
- [ ] QUICKSTART.md — one-command startup guide
- [ ] USER_GUIDE.md — Telegram commands + web tracker usage
- [ ] **Setup / Prerequisites doc** — external repos must be cloned alongside agent-hub:
  - `callback-cv` (🔴 mandatory) — filesystem path `../callback-cv`; provides PROFILE.md + cv_to_pdf.py
  - `knowledge-mirror-parser` (🟠 for URL fetch) — HTTP service `KMP_BASE_URL`; docker-compose builds from `../knowledge-mirror-parser`
  - `job-board-monitor` (🟢 optional) — produces `seen_jobs.json` for auto-discovery; or use `scripts/emit_vacancy.py`
  - Document the default sibling-folder layout (all repos under one parent dir) + env-var overrides
- [ ] **Decide multi-repo onboarding strategy** — explicit clone instructions vs bootstrap script vs git submodules.
  - ⚠️ Constraint: `callback-cv` holds PROFILE.md (personal data) — must NOT become a public submodule.
  - Likely split: public tools (kmp) via submodule/script; callback-cv stays user-provided private repo.

---

## ✅ Done

### P0 — Core
- DB: schema.sql + database.py + init + migration (import_tracker.py, 46 vacancies)
- LLM client: ClaudeProvider + prompt caching + AGENT_MODE=testing confirmation guard
- Adapters: KMPAdapter (httpx), CVAdapter (subprocess)
- Contracts: ParsedDocument, AnalysisResult, CVResult
- Telegram: aiogram 3.x, long polling, callback_query, inline keyboards
- Router: PydanticAI Agent + tool_registry.py
- Prompts: phase1–phase4 (all 5 files)
- CV Tools: cv_fetch_jd, cv_analyze, cv_generate, cv_cover, cv_get_tracker
- Web tracker: web/api.py + web/templates/tracker.html + web/reader.py
- RSS Watcher: core/rss_watcher.py + scripts/emit_vacancy.py
- File logging: RotatingFileHandler (logs/agent.log, 5MB×5)
- Timing + DB state machine logs
- Dockerfile + docker-compose.yml (kmp-service + agent-hub + web-tracker)
- scripts/start_tracker.bat, scripts/e2e_test.py, scripts/import_tracker.py
- .env.example, .gitignore

### P1 — Integration
- knowledge-mirror-parser: POST /parse endpoint (already existed), site configs for djinni.co + jobs.dou.ua
- e2e fetch + analyze verified on real DOU URL (vacancy #47, fit 6.5/10)
- tests/test_web_reader.py — 43 tests
