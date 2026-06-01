# EPIC 01–12 — Pre-Pivot Archive

**Phase:** Pre-pivot (agent-hub era)
**Status:** ✅ All done
**Archived:** 2026-06-01 (pivot to career-agent focused vertical)

---

All EPIC 01–12 were implemented as part of the original agent-hub build.
Full implementation details in git history up to commit `c951ced`.

## Summary of completed work

### EPIC-01–04 — Foundation
- Contracts: `ParsedDocument`, `AnalysisResult`, `CVResult`
- Adapters: `KMPAdapter` (httpx → kmp-service), `CVAdapter` (subprocess → callback-cv)
- DB: `schema.sql` + `database.py` (aiosqlite, init, migration, import_tracker)
- LLM client: `ClaudeProvider` — prompt caching, extended thinking, `AGENT_MODE=testing` guard

### EPIC-05–06 — UI + Routing
- Telegram: aiogram 3.x, long polling, inline keyboards, `callback_query`
- Router: PydanticAI `Agent[AgentDeps, str]`, `ToolRegistry`
- Entry point: `agent.py` startup sequence

### EPIC-07–09 — CV Pipeline
- `cv_fetch_jd`: URL → KMPAdapter → JD.md → SQLite
- `cv_analyze`: Phase 1+2 → JD_analysis.md + Quick Scan
- `cv_generate`: Phase 3+3.5 → CV.md + PDF via CVAdapter

### EPIC-10 — Cover Letter
- `cv_cover`: Phase 4 → Cover.md → Telegram delivery

### EPIC-11 — Web Tracker
- `web/api.py` (FastAPI), `web/templates/tracker.html` (HTMX + Jinja2)
- `web/reader.py` — 43 tests

### EPIC-12 — Ops
- RSS Watcher: `core/rss_watcher.py`, `scripts/emit_vacancy.py`
- Logging: `RotatingFileHandler` (5MB × 5)
- Docker: `Dockerfile` + `docker-compose.yml` (kmp-service + career-agent + web-tracker)
- Scripts: `start_tracker.bat`, `e2e_test.py`, `import_tracker.py`
- `.env.example`, `.gitignore`
