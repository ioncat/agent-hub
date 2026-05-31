# Effort Log — agent-hub

Time analysis based on git history (commit timestamps).

## Methodology

Time estimated by **commit clusters**, not calendar day. Handles multiple sessions
per day with reasonable accuracy.

**Rules:**

1. **Cluster** = sequence of commits with gaps ≤ 1 hour between consecutive commits.
   Gap > 1 hour ends the cluster and starts a new one.
2. **Session time** = timestamp of last commit in cluster − timestamp of first commit.
3. **Single-commit cluster** → estimated at **~15 min** (minimum).
4. Multiple clusters in one day → multiple rows.
5. Time before first commit (planning, discussion) and after last commit (testing)
   is NOT counted — the number is a lower bound on real time.
6. Commits across related repos (knowledge-mirror-parser, callback-cv) included
   when they fall in the same cluster window.

**Why this works:** cluster-based estimation reflects actual work cadence without
manual tracking. Git history is the source of truth.

---

## Session log

| Date | Commits | Work description | Session time |
|------|---------|-----------------|-------------|
| 28.05.2026 | 1 (agent-hub) | **Architecture design session**: project vision, technology stack decisions (PydanticAI, aiogram 3.x, httpx, aiosqlite), adapter pattern, contract-first design, HTTP-first service separation, async safety analysis, EPIC-1 HTML inspection (Djinni/DOU CSS selectors via curl). Init commit: BACKLOG.md, Q&A notes. ⚠️ Highly understated — most work was pre-commit design discussion. | ~15 min (git lower bound) |
| 29.05.2026 | 22 (agent-hub) + 1 (kmp) | **EPIC-1**: ARCHITECTURE.md, delivery docs, docker-compose, kmp FastAPI endpoint, `contracts/parsed_document.py`, `adapters/kmp_adapter.py`. **EPIC-2**: `db/schema.sql` + `db/database.py` (7 CRUD helpers), 10 tests. **EPIC-3**: `core/llm_client.py` (ClaudeProvider cache_control=ephemeral, OllamaProvider stub), 12 tests. **EPIC-4**: `core/telegram.py` (aiogram 3.x, chat_id guard, inline keyboards, split helper). **EPIC-5**: `core/tool_registry.py`, `core/router.py` (PydanticAI Agent), `core/settings.py`, `agent.py` entry point. **EPIC-6**: 5 prompt files extracted from SKILL.md (`phase1–4.md`). **EPIC-7**: `tools/cv_fetch_jd.py` + `core/deps.py` (AgentDeps DI pattern), 15 tests. **EPIC-8**: `tools/cv_analyze.py` (Phase 1+2, Quick Scan extraction), 15 tests. **EPIC-9**: `tools/cv_generate.py` (Phase 3+3.5, SUMMARY split), `adapters/cv_adapter.py` (subprocess→pdf), 20 tests. Effort log created. 100/100 tests. ⚠️ Spanned 2 context windows; effort log written mid-session. | ~2 h 31 min (17:29–20:00) |
| 29.05.2026 *(2nd cluster)* | 6 (agent-hub) | **EPIC-10**: `tools/cv_cover.py` (Phase 4, Cover.md → Telegram). **EPIC-11**: `tools/cv_get_tracker.py` (SQLite → Telegram summary, fit score regex). **Logging**: `time.monotonic()` timing on all LLM + HTTP calls; DB state machine transition logs. **RSS Watcher**: `core/rss_watcher.py` (asyncio.Task, polls seen_jobs.json, seeds from DB on start), `scripts/emit_vacancy.py`. **import_tracker**: `scripts/import_tracker.py` reads callback-cv/tracker.json → 46 vacancies into SQLite (1 true dupe skipped). **EPIC-12 Web tracker**: `web/reader.py` (VacancyView + regex parsers), `web/api.py` (FastAPI standalone, markdown Jinja2 filter), `web/templates/tracker.html` (CSS+JS from callback-cv verbatim, Jinja2 loop). BACKLOG.md cleaned up — done items moved to ✅ section. | ~44 min (20:59–21:43) |
| 30.05.2026 | — (no commits during session) | **Token economics & quality tuning**: Extended Thinking enabled (budget=10k) for phase1+2 in `ClaudeProvider.complete()` with auto max_tokens raise; model switched to `claude-sonnet-4-6`; SDK 0.105.2 — `betas` param removed (caching now GA). DB schema expanded: `profile_tokens`, `prompt_tokens`, `user_tokens`, `budget_tokens`, `thinking_tokens`, `elapsed_ms` in `llm_usage`. Prompt overhaul: language rule repositioned directly before Output Format; analytical tone rule added; Quick Scan code fence removed (caused empty output). Test runs v3 (Quick Scan bug found) → v4 (fixed, Russian output confirmed). Billing analysis: first CSV had lag, formula `_calc_cost()` confirmed correct — thinking tokens billed as output at $15/MTok. `docs/discovery/Tokenomics.md` fully updated; old `.claude/memory/token-tracking.md` deleted. | ~4 h (estimated) |
| 31.05.2026 | 1 (agent-hub) + 1 (callback-cv) | **Phase 2 redesign & pipeline evolution**: Analyzed v4 quality vs original callback-cv output (external review file). Phase 2 prompt full rewrite: 3-way Verdict, Key Barriers/Hidden Risks/Warnings separation, explicit scoring guidance (baseline 5.0, numeric deltas), mandatory Fit Breakdown ✅/⚠️/❌, conditional Adaptation Plan, Internal Analysis section. Phase 1/3/3.5 minor updates (archetype-aware). PROFILE.md `Archetype & Role Positioning` section added. ARCHITECTURE.md `User Profile Schema`. BACKLOG.md: onboarding fields, Pipeline Cost Preview P1 feature. v5 broken (prompt `###` vs `##` header conflict), v6 fixed and working — score 5.5/10, full 4-section Phase 2. Billing verified: v5+v6=$0.22, formula ✅. `Pipeline-Evolution.md` created. | ~3 h 30 min (estimated) |
| **Total** | | | **~11 h** |

*Table updated after each session.*
