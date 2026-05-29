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
| 29.05.2026 | 10 (agent-hub) + 1 (kmp) | **EPIC-1**: ARCHITECTURE.md, delivery docs (BACKLOG, EPIC-1..3, conventions), docker-compose, knowledge-mirror-parser FastAPI endpoint (`api.py`, `config.py` Djinni+DOU selectors, Dockerfile), `contracts/parsed_document.py`, `adapters/kmp_adapter.py`, `requirements.txt`. **EPIC-2**: `db/schema.sql` (vacancies + pipeline_runs, WAL, FK cascade), `db/database.py` (init_db, get_db, 7 CRUD helpers), `tests/test_db.py` (10/10). **EPIC-3**: `core/llm_client.py` (LLMClient Protocol, ClaudeProvider with cache_control=ephemeral, OllamaProvider stub, LLMError hierarchy), `tests/test_llm_client.py` (12/12). 22 tests total, all green. | ~1 h 24 min (17:29–18:53) |
| **Total** | | | **~1 h 39 min** |

*Table updated after each session.*
