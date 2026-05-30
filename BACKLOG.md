# agent-hub — Backlog

> Last updated: 2026-05-30

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
