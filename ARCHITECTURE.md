# agent-hub — Architecture & Design

> Status: pre-development / design phase
> Last updated: 2026-05-29

---

## Vision

Personal AI agent that orchestrates multiple specialized services via tool use.
First domain: CV/job application pipeline. Designed to extend to any personal workflow.

**Core idea:** Agent = thin orchestration layer. Each domain = a set of tools. Adding a new domain = new tool file only, no core changes. Services stay autonomous, communicate via HTTP contracts.

**Portfolio rationale:** Demonstrates multi-tool AI agent pattern — independent services with HTTP contracts, human-in-the-loop via Telegram, async pipeline, Claude API with prompt caching, adapter-based dependency management.

---

## Service Map

| Repo | Role | Status | Interface |
|------|------|--------|-----------|
| `job-board-monitor` | RSS watcher → new job discovery | ✅ Done | `seen_jobs.json` (filesystem) |
| `knowledge-mirror-parser` | URL → clean Markdown | ✅ Done | **HTTP** `POST /parse` |
| `callback-cv` | Analysis prompts + PROFILE + cv_to_pdf | ✅ Done | Filesystem + subprocess |
| `agent-hub` | Orchestration + Telegram UI + routing + web | 🔧 This repo | — |

---

## Project Structure

```
agent-hub/
├── core/
│   ├── telegram.py           — aiogram 3.x, long polling, inline keyboards, callback_query
│   ├── tool_registry.py      — generic tool registration
│   ├── router.py             — PydanticAI Agent: routes intent → tool call (LLMClient via DI)
│   └── llm_client.py         — LLM abstraction: ClaudeProvider (primary), stub fallback
│
├── adapters/                 — all external service calls isolated here
│   ├── kmp_adapter.py        — KMPAdapter: HTTP → knowledge-mirror-parser
│   └── cv_adapter.py         — CVAdapter: filesystem + subprocess → callback-cv
│
├── contracts/                — typed return types (Pydantic BaseModel)
│   ├── parsed_document.py    — ParsedDocument(title, markdown, source_url)
│   └── cv_result.py          — CVResult, AnalysisResult, etc.
│
├── tools/
│   ├── cv_fetch_jd.py        — URL → JD.md via KMPAdapter → SQLite
│   ├── cv_analyze.py         — Phase 1+2: JD + prompts + PROFILE → Claude API → JD_analysis.md
│   ├── cv_generate.py        — Phase 3+3.5: CV draft → self-review → approve → [Name]_CV.pdf
│   ├── cv_cover.py           — Phase 4: cover message → Telegram text
│   └── cv_get_tracker.py     — SQLite query → formatted Telegram summary
│
├── prompts/                  — API-clean prompt files (no Claude Code artifacts)
│   ├── phase1_analysis.md
│   ├── phase2_fit.md
│   ├── phase3_cv_draft.md    — CV generation (output NOT shown to user)
│   ├── phase3_5_review.md    — self-review applied to draft → shown + approved → saved
│   └── phase4_cover.md
│
├── web/
│   ├── api.py                — FastAPI: /vacancies, /vacancies/{id}
│   └── templates/
│       └── tracker.html      — HTMX + Jinja2
│
├── db/
│   └── schema.sql            — SQLite schema
│
├── config/
│   ├── profile.yaml          — service URLs, Telegram chat IDs, paths
│   └── llm.yaml              — LLM provider config
│
└── agent.py                  — entry point: asyncio event loop, two tasks
```

---

## Adapter Pattern

**Principle:** agent-hub depends only on contracts, not on service internals.

```
agent-hub tools
      ↓
  KMPAdapter.fetch_markdown(url) → ParsedDocument
      ↓
  POST http://kmp-service/parse
      ↓
  knowledge-mirror-parser (internal implementation irrelevant)
```

**Typed contracts** — adapters return Pydantic models, never raw service objects:

```python
# contracts/parsed_document.py
class ParsedDocument(BaseModel):
    title: str
    markdown: str
    source_url: str

# adapters/kmp_adapter.py
class KMPAdapter:
    async def fetch_markdown(self, url: str) -> ParsedDocument:
        resp = await httpx.post(f"{self.base_url}/parse", json={"url": url})
        return ParsedDocument(**resp.json())
```

If knowledge-mirror-parser changes its parser engine, adds Redis, switches libraries — agent-hub notices nothing. Contract unchanged = zero impact.

**Future-proof:** today adapter wraps HTTP. If service moves, adapter changes. Tools never change.

---

## Async Architecture

Production-grade, non-blocking throughout.

```
agent.py  —  single asyncio event loop
├── Task 1: TelegramPoller   (aiogram 3.x long polling)
├── Task 2: RSSWatcher       (periodic asyncio.sleep, polls seen_jobs.json)
└── TaskQueue                (asyncio.Queue)
         ↓
    WorkerPool
    ├── fetch worker   — httpx async (calls kmp-service HTTP)
    └── llm worker     — PydanticAI + Anthropic async SDK
```

**Telegram:** aiogram 3.x (async-native).
**HTTP calls:** httpx (async, not requests).
**No blocking I/O** on event loop.

---

## Deployment

**Day 1 — Docker Compose (two containers):**
```
docker-compose.yml
├── agent-hub          :8080  — Telegram bot + web tracker + agent logic
│     ├── httpx → kmp-service:8001
│     ├── shared volume: vacancies/
│     └── SQLite: /data/vacancies.db
│
└── kmp-service        :8001  — knowledge-mirror-parser + FastAPI endpoint
      └── POST /parse → returns ParsedDocument JSON
```

**callback-cv** stays on host filesystem — agent-hub mounts `vacancies/` as shared volume, calls `cv_to_pdf.py` via subprocess.

**Future — full microservices:**
- callback-cv gets its own container + HTTP API
- Adapters switch from subprocess/filesystem to HTTP (no changes in tools layer)

---

## Vacancy Input Paths

**Path 1 — Automated (Djinni / DOU RSS):**
```
RSS feed → job-board-monitor detects new vacancy
  → RSSWatcher picks up from seen_jobs.json
  → tool: cv_fetch_jd(url, source)
      → KMPAdapter.fetch_markdown(url) → HTTP → kmp-service
      → writes: vacancies/[folder]/JD.md
      → SQLite: INSERT vacancy (status=new)
  → Telegram: "🆕 Product Manager at X — Djinni
               [✅ Analyze] [❌ Skip]"
```

**Path 2 — Semi-manual (LinkedIn / other):**
```
User drops JD.md into vacancies/[folder]/
  → agent detects new folder (polling)
  → SQLite: INSERT vacancy (status=new, source=manual)
  → Telegram notification → continues from Analyze step
```

**RSS sources:** Djinni + DOU. Already filtered to PM/PO roles — no LLM pre-filter needed.

---

## Full CV Pipeline Flow

```
[vacancy status=new in SQLite + JD.md on filesystem]
  ↓
tool: cv_analyze(vacancy_id)
  → reads: JD.md + prompts/phase1_analysis.md + prompts/phase2_fit.md
  → Claude API (cached system prompt: PROFILE.md)
  → writes: JD_analysis.md
  → SQLite: UPDATE status=analyzed, fit_score, recommendation
  ↓
Telegram → user:  [Quick Scan from JD_analysis.md]
  "✅ Анализ готов
   📊 Fit: 8/10 · ✅ Подавать
   Category: Discovery + Strategy PM
   Warnings: B2B only; 5 шагов найма
   [📄 Generate CV] [📋 Tracker] [❌ Skip]"
  ↓ user taps 📄
  ↓
tool: cv_generate(vacancy_id)
  ├── Phase 3: prompts/phase3_cv_draft.md + PROFILE.md → Claude API → CV draft
  │   [draft NOT shown to user]
  ├── Phase 3.5: prompts/phase3_5_review.md + draft → Claude API → self-review
  │   Telegram: shows self-review + CV text for approval
  │   [user approves / requests changes]
  ├── → writes: [Name]_CV.md
  ├── → CVAdapter.to_pdf([Name]_CV.md) → subprocess cv_to_pdf.py → [Name]_CV.pdf
  └── → SQLite: UPDATE status=cv_ready
  ↓
Telegram: sends [Name]_CV.pdf as file attachment
  "📄 CV готов  [✉️ Cover message] [✅ Done]"
  ↓ user taps ✉️ (explicit, not auto)
  ↓
tool: cv_cover(vacancy_id)
  → prompts/phase4_cover.md + JD_analysis.md + PROFILE.md → Claude API
  → Telegram: cover text as message
  → writes: [Name]_Cover.md
  → SQLite: UPDATE status=cover_ready
```

---

## Prompt Architecture

**Prompt caching** is a first-class architectural element.

```python
# core/llm_client.py — ClaudeProvider
system_prompt = [
    {"type": "text", "text": PROFILE_MD,   "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": phase_prompt, "cache_control": {"type": "ephemeral"}},  # also cached
]
```

Both system blocks cached → charged once per 5-min TTL. Only the user turn (JD + prior-phase
output) is uncached. ~3 API calls per CV session → static content cached after the first call.

**Prompt files** (`agent-hub/prompts/`) — API-clean, no Claude Code artifacts, no file-save instructions. Agent handles all I/O.

**Phase 3 → 3.5 sequence:**
1. Claude with `phase3_cv_draft.md` → CV text (hidden)
2. Claude with `phase3_5_review.md` + CV text → self-review
3. Show both to user → approve → save + PDF

---

## Storage Architecture

**Hybrid: SQLite metadata + filesystem documents**

```sql
CREATE TABLE vacancies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,     -- 'djinni' | 'dou' | 'manual'
    url             TEXT,
    title           TEXT NOT NULL,
    folder_path     TEXT NOT NULL,     -- YYYY-MM-DD_source_slug
    status          TEXT NOT NULL DEFAULT 'new',
                                       -- new → analyzed → cv_ready → cover_ready → done | skipped
    fit_score       REAL,
    recommendation  TEXT,              -- 'подавать' | 'не подавать'
    category        TEXT,
    warnings        TEXT,
    blockers        TEXT,
    cv_path         TEXT,
    pdf_path        TEXT,
    cover_path      TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Filesystem** — documents only:
- `vacancies/[YYYY-MM-DD_source_slug]/JD.md`
- `vacancies/[folder]/JD_analysis.md`
- `vacancies/[folder]/[Name]_CV.md` + `.pdf`
- `vacancies/[folder]/[Name]_Cover.md`

**tracker.json** → replaced by SQLite.

---

## Web Tracker

**FastAPI + HTMX + Jinja2** — no npm, no JS framework.

```
web/api.py
├── GET  /                       → tracker.html
├── GET  /api/vacancies          → JSON list
├── GET  /api/vacancies/{id}     → single vacancy + full analysis
└── POST /api/vacancies/{id}/status → update status
```

FastAPI serves as internal API for agent tools AND future external integrations.

---

## LLM Client

```python
class LLMClient:
    async def complete(self, messages, tools=None):
        try:
            return await self.primary.complete(messages, tools)
        except (RateLimitError, OverloadedError):
            await telegram.notify("⚠️ Claude недоступен. Попробуйте позже.")
            raise  # no silent degradation for analysis tasks

class OllamaProvider(BaseLLMProvider):
    async def complete(self, ...):
        raise NotImplementedError("Local LLM fallback not yet implemented")
```

---

## Telegram Output Format

| Output | Format |
|--------|--------|
| New vacancy notification | Text + inline buttons |
| Analysis result | Text — Quick Scan (fit, rec, warnings) + buttons |
| CV self-review | Text — review findings + approve buttons |
| CV file | **PDF attachment** |
| Cover message | **Text message** |
| Tracker summary | Text — top N vacancies with status |

---

## Open Questions

- [ ] **knowledge-mirror-parser configs:** Djinni + DOU `content_selector` (need HTML inspection)
- [ ] **Prompt caching via PydanticAI:** verify `cache_control: ephemeral` passes through correctly
- [ ] **kmp-service port config:** in `profile.yaml` or env var

---

## User Profile Schema

**Current state:** single user (Oleksii Bondarenko). Profile lives in `callback-cv/skill/PROFILE.md`.

**Profile file** (`PROFILE.md`) is the canonical source of user identity for all LLM calls.
Sent as first cached system block on every Claude API call (`cache_control: ephemeral`).

### Required fields (current schema)

| Field | Location | Description |
|-------|----------|-------------|
| Name variants | PROFILE.md `## Name variants` | EN formal/informal + native |
| Contact info | PROFILE.md header | email, Telegram, LinkedIn, GitHub |
| Summary | PROFILE.md `## Summary` | 3–5 sentence positioning statement |
| Experience | PROFILE.md `## Experience` | Chronological, metrics-backed |
| Skills / Certs | PROFILE.md | Top skills, languages, certifications |
| Honest Gaps | PROFILE.md `## Honest Gaps` | Things LLM must never fabricate |
| **Archetype** | PROFILE.md `## Archetype & Role Positioning` | See below |

### Archetype field (added 2026-05-31)

`archetype_preference: execution | founder | dual`

Drives Phase 2 analysis behavior:
- **execution** — emphasize delivery track, metrics, coordination
- **founder** — emphasize 0→1, co-founder experience, autonomy
- **dual** — LLM checks JD archetype signal, picks framing dynamically

Archetype delta (JD archetype ≠ CV framing) generates **both**:
- Warning: flags the mismatch for user attention
- Adaptation Plan: specific reframing advice from the matching archetype section

### Multi-user (planned — BACKLOG P2)

When generalized: each user gets isolated `PROFILE.md` + vacancies folder + DB namespace.
Onboarding collects all schema fields above via Telegram conversation.
See `BACKLOG.md → P2 — Onboarding` for full field list.

---

## Design Decisions Log

**2026-05-28:**
- Multi-service architecture — services stay autonomous, agent orchestrates via tool calls
- Telegram is primary UI
- Agent framework not decided

**2026-05-29 — Session 1:**
- LLM abstraction with fallback stub (Claude primary, Ollama NotImplemented)
- Long polling, bidirectional Telegram (aiogram 3.x)
- Both trigger modes: RSS auto + manual folder drop
- knowledge-mirror-parser for JD fetching — add Djinni + DOU configs
- Analysis = Claude API call with SKILL.md prompts + PROFILE.md
- PROFILE.md is user-configurable (current: Oleksii Bondarenko)
- RSS: Djinni + DOU (no LLM pre-filter)
- SQLite + filesystem hybrid storage
- FastAPI + HTMX + Jinja2 web tracker
- Prompt caching as first-class element
- Phase 3→3.5 CV draft hidden, shown only after self-review

**2026-05-29 — Session 2:**
- **PydanticAI** as agent framework. Evaluated: OpenClaw/NanoClaw (platforms, wrong category), LangGraph (overhead), CrewAI (multi-agent pattern mismatch), direct SDK (more boilerplate). PydanticAI: same ecosystem as FastAPI, type-safe, DI built-in, multi-agent ready.
- **HTTP from day 1** — knowledge-mirror-parser gets FastAPI endpoint, agent-hub calls via httpx. Removes aiohttp rewrite blocker. Cleaner service boundaries for portfolio.
- **Adapter layer** (`core/adapters/`) — all external calls isolated. Agent-hub depends on contracts, not internals.
- **Typed contracts** (`core/contracts/`) — Pydantic BaseModel return types. `ParsedDocument`, `AnalysisResult`, etc.
- **pip install -e removed** — HTTP replaces Python imports for knowledge-mirror-parser.
- **callback-cv** remains filesystem + subprocess (no HTTP needed for Phase 1).
- **Dependency management:** adapter layer + contract tests + version pinning. Update = explicit event (run tests, bump version).
- **Docker Compose from day 1** — two containers: agent-hub + kmp-service.
