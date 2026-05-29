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
| **Total** | | | **~2 h 46 min** |

*Table updated after each session.*
