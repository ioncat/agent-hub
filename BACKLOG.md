# career-agent — Backlog

> Last updated: 2026-06-02
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
| [EPIC-20](docs/delivery/Epics/EPIC-20-vacancy-path-standard.md) | Unified vacancy path standard | 📋 Planned |

---

## ✅ P1 — Batch inbox: fix move-to-clean-folder flow (2026-06-02)

- `scripts/vacancy_track.py` — added `delete-inbox` subcommand (path traversal guard, idempotent)
- `skill/SKILL.md` — Batch Mode + Sequential Mode: `move-to-inbox` → `delete-inbox`
- Cleaned up stray duplicate `Senior Technical Product Manager AI — DOIT Software` folder

---

## ✅ P1 — Inbox deduplication (2026-06-02)

- `skill/SKILL.md` — Sequential Mode: step a.5 dedup (URL grep → skip/reprocess prompt)
- `skill/SKILL.md` — Batch Mode: silent dedup, `♻️ уже обработана` in table
- `.claude/commands/analyze.md` — step 3 dedup note added before inbox menu

---

## P1 — Testing & Operations

### 🟡 e2e_test.py — integration verification

**What:** manual integration test. Hits real Claude API + real services. Costs tokens.
**When to run:** after changes to cv_generate / cv_cover / cv_analyze / ClaudeProvider / CVAdapter, after major EPIC merge, when something seems broken.
**Not for:** scheduled monitoring (costs money). Use health_check.py for that.

**Prerequisites:** jd-parser :8001 + pdf-service :8002 running + ANTHROPIC_API_KEY in .env

```bash
# Start services if not running:
cd services/pdf && python -m uvicorn app:app --port 8002 &

# Run e2e (interactive terminal — answers y/n manually):
python scripts/e2e_test.py --id 48 --phase generate,cover

# Or non-interactive (auto-confirms all API calls):
python scripts/e2e_test.py --id 48 --phase generate,cover --auto-confirm
```

- [x] Contract Tests: ParserAdapter + CVAdapter (mock)
- [x] **e2e verify: generate+cover** — vacancy #48, CV.md ✅ PDF ✅ Cover.md ✅ ($0.10, 2026-06-02)
  - Fixed: `services/pdf/render.py` font path was relative `services/pdf/fonts/` → now absolute `_PROJECT_ROOT/fonts/`
  - Fixed: added `load_dotenv` to render.py so pdf-service picks up .env on startup
- [ ] e2e verify: full pipeline from URL (fetch → analyze → generate → cover)

### ✅ health_check.py — lightweight service monitor (2026-06-02)

- `scripts/health_check.py` — implemented: parser + pdf-service HTTP checks, SQLite SELECT 1, optional Telegram bot ping + alert on failure
- Exit 0 = all OK, exit 1 = any failure
- `--telegram` flag: also check bot token validity + send alert if down
- `--parser-url` / `--pdf-url` overrides for non-default ports

```bash
python scripts/health_check.py            # basic
python scripts/health_check.py --telegram # + bot check + alert
```

- [ ] Wire to Windows Task Scheduler (recurring)

### 🟡 Contract Tests
- [x] `tests/test_parser_adapter.py` — ParserAdapter: mock httpx, test parse/error/health paths
- [x] `tests/test_cv_adapter.py` — CVAdapter: mock httpx, happy path/error/network/construction (11 tests)

### 🟡 Multi-skill architecture
**Status: ✅ Phase 1 done (2026-06-01)**
- [x] `prompts/pm/` + `prompts/generic/` — all 5 phases per skill type
- [x] `skill_type` routing in all tools (cv_analyze, cv_generate, cv_cover)
- [x] `AgentDeps.skill_type` — default `'pm'`, seeded from DB user row
- [x] Tested: PM pipeline (SOLAR Digital ✅) + Generic pipeline (AlphaNova ✅)

**Phase 2:**
- [x] `skill_type` question in Telegram `/start` FSM — already in EPIC-17 Phase 1 (`core/telegram.py` line 268)

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

## P1 — Детерминированный pipeline: минимизировать роль агента

**Идея (2026-06-02):** Агент плохо следует инструкциям в детерминированных задачах (форматирование файлов, структура шаблонов, алгоритмические шаги). Там, где результат предсказуем — заменить агента на код.

**Принцип:** Агент генерирует *контент* (текст, аргументы). Программа берёт контент и преобразует его по жёсткому шаблону — без участия агента.

**Пример уже реализован:** Агент пишет `## Quick Scan` в Markdown → `cv_to_pdf.py` рендерит в PDF по фиксированному шаблону (verdict banner, dot-bar, two-column layout). Агент не управляет версткой.

**Где применить:**
- [ ] Структура `JD_analysis.md` — сделать строгий шаблон с плейсхолдерами; агент заполняет значения, скрипт собирает файл
- [ ] Структура `[Name]_CV.md` — агент генерирует секции по фиксированным якорям (`<!-- SUMMARY -->`, `<!-- EXPERIENCE -->` и т.д.)
- [ ] Inbox processing flow — извлечь алгоритмические шаги (dedup, move, register) в скрипт; агент только анализирует контент
- [ ] Пересмотреть все шаги `skill/SKILL.md` — разделить: что делает агент (генерация), что делает код (файловые операции, форматирование, регистрация в DB)

**Связано с:** P1 — PDF template system, EPIC-19 local execution mode

---

## P1 — PDF template system (шаблонизатор)

**Направление (2026-06-02):** Отказаться от fpdf2 + ручного рендеринга. Перейти на HTML-шаблоны, конвертируемые в PDF скриптом — без участия агента.

**Принцип:**
- Агент генерирует контент (текст, данные)
- Скрипт подставляет данные в HTML-шаблон
- Скрипт конвертирует HTML → PDF (weasyprint или playwright)
- Emoji, отступы, цвета — полностью в CSS, не в коде рендерера

**Почему:** fpdf2 не поддерживает emoji нормально, сложное форматирование и межблочные отступы требуют ручного управления. Попытка добавить emoji через seguisym.ttf — работает, но только ч/б.

- [ ] Выбрать рендерер: weasyprint vs playwright (headless Chrome)
- [ ] Создать HTML-шаблон для JD_analysis (Quick Scan, Fit Breakdown, Self-Review)
- [ ] Создать HTML-шаблон для CV
- [ ] Скрипт: принимает .md / JSON → рендерит HTML → сохраняет PDF
- [ ] Документировать в `docs/discovery/pdf-design-system.md`

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

### Batch mode for inbox (2026-06-02)
- **Trigger**: 3+ вакансій в inbox → автоматично batch mode (без флагів)
- **Flow**: "Обробляємо N вакансій..." → Phase 1+2 тихо по всіх → зведена таблиця → Approve / Try chance / Пропустити
- **Таблиця**: #, Компанія — Роль, Src, Fit, Рекоменд. (✅/⚠️/❌), Рівень/$, Ключовий gap; сортування ✅→⚠️→❌ + fit DESC
- **Sequential mode**: 1–3 вакансій → поведінка без змін
- **move-processed**: після Phase 1+2 (незалежно від рішення про Phase 3+4)

### URL deduplication + Local mode → Tracker (2026-06-02)
- **`normalize_url()`** — strips UTM/tracking params, trailing slash, lowercases host; all boards safe (IDs in path)
- **`extract_site()`** — auto-infers djinni/dou/linkedin/hh/other from URL hostname
- **`insert_vacancy()`** — always stores normalized URL; auto-infers site when not explicit
- **`get_vacancy_by_url()`** — matches on `normalized OR original` (legacy fallback for existing UTM rows)
- **`scripts/vacancy_track.py`** — lightweight CLI: `upsert` (idempotent, prints vacancy_id) · `update` (status + path) · `move-processed` (inbox → processed/)
- **`/analyze` + `SKILL.md`** — DB write + processed/ move steps wired into inbox processing flow
- **Tests** — +14 dedup/normalize/extract tests; 279/279 ✅

### Tracker: source grouping + site filter (2026-06-02)
- **`site` field exposed in tracker** — grouping rows by date → source (DOU / Djinni / LinkedIn); recommended first within each source group
- **Site chip per row** — colored badge (DOU green, Djinni blue, LinkedIn navy) visible at all times, survives JS sort
- **Source filter dropdown** — "All sources / Djinni / DOU / LinkedIn / Other"; state persisted in localStorage
- **Smart source-sep hide** — source separator hidden when filter removes all its rows
- **Sort** — `web/api.py`: date DESC → site ASC → rec_order (recommended=0, other=1, not-recommended=2)
- **`site_display` property** — `VacancyView`: djinni→Djinni, dou→DOU, linkedin→LinkedIn, unknown→capitalize
- **Tests** — 6 new `TestSiteDisplay` tests; full suite 259/259 ✅

### Skill pipeline improvements (2026-06-02)
- **Mode selection (Step 0)** — `/analyze` now asks Local vs API mode as the very first step, before inbox check and profile load; mode applies to entire session; `-l` and `-inbox` flags skip mode question
- **Inbox manual drop zone** — `vacancies/inbox_manual/` folder: drop `.md`/`.txt` files; checked on every `/analyze`; first-line URL → fetch pipeline, otherwise JD text; on success → moved to `processed/`; multi-file batch support; profile selection if multiple users
- **Cover letter two variants** — Phase 4 now always generates Variant A (narrative) + Variant B (bullets) side-by-side; templates in `prompts/pm/phase4_cover.md`
- **Ukrainian CV: no РЕЗЮМЕ header** — Rule 15 in `prompts/pm/phase3_cv_draft.md`: Ukrainian CV summary flows directly after headline, no section header
- **PDF paragraph spacing fix** — `cv_to_pdf.py`: `ln(1)` → `ln(4)` in `paragraph()` method; eliminates merged paragraphs in all CVs
- **Legacy KMP cleanup** — `kmp` → `parser` in tests, scripts, tool docstrings, EPIC-15 doc; no functional change
