# Epic 11: Tracker Summary Tool

**Status:** 🟢 Done
**Phase:** 2 — CV Pipeline
**Priority:** 🟡 P2
**Blocks:** EPIC-12 (Web tracker)

---

## Strategic Context

Provides visibility into the vacancy pipeline without opening files or the web tracker.
Pure read-only tool: no LLM call, no writes. Lists recent vacancies with status and
fit scores extracted from JD_analysis.md on disk.

---

## Goal

`tools/cv_get_tracker.py` exposes `cv_get_tracker(ctx, limit=20, status=None) → str`.
Registered in `agent.py` ToolRegistry.

---

## Output Format

```
📊 Трекер вакансий — 3 записи

1. ✅ cover_generated — Backend Dev [djinni] · Fit 8/10 · 2026-05-29
2. 🔬 analyzed — Product Manager [djinni] · Fit 7/10 · 2026-05-28
3. 📄 fetched — iOS Developer [dou] · — · 2026-05-27
```

Status emoji mapping:

| Status | Emoji |
|--------|-------|
| fetched | 📄 |
| analyzed | 🔬 |
| cv_generated | 📝 |
| cover_generated | ✅ |
| error | ❌ |

---

## Fit Score Extraction

Reads `JD_analysis.md` next to `JD.md` (vacancy folder) and searches for:

```
**Fit score:** 8/10
```

Returns `"—"` if:
- `markdown_path` is None
- `JD_analysis.md` does not exist
- Pattern not found in file
- File read fails (OSError)

Extraction is **best-effort and non-fatal** — tracker never crashes on missing files.

---

## Parameters

| Param | Default | Purpose |
|-------|---------|---------|
| `limit` | 20 | Max vacancies to show |
| `status` | None | Optional filter by status value |

---

## User Stories

### US-1101: List all recent vacancies

**Given** DB has vacancies
**When** `cv_get_tracker(ctx)` called
**Then** return formatted list, latest first, up to 20 entries

### US-1102: Filter by status

**Given** user asks "show analyzed vacancies"
**When** `cv_get_tracker(ctx, status='analyzed')` called
**Then** only analyzed vacancies returned

### US-1103: Empty DB

**Given** no vacancies in DB
**When** `cv_get_tracker(ctx)` called
**Then** friendly message explaining how to add first vacancy

### US-1104: Fit score from JD_analysis.md

**Given** vacancy has JD_analysis.md with Quick Scan
**When** tracker renders
**Then** fit score shown (e.g. "Fit 8/10")

### US-1105: JD_analysis.md missing

**Given** vacancy has no JD_analysis.md
**When** tracker renders
**Then** fit shown as "—", no exception

---

## Implementation

| File | Change |
|------|--------|
| `tools/cv_get_tracker.py` | New — tracker tool + `_format_row` + `_extract_fit_score` |
| `agent.py` | Register `cv_get_tracker` in `_register_tools` |

---

## Acceptance Criteria

- Calls `database.list_vacancies(status, limit)` — no raw SQL in tool
- `_extract_fit_score` never raises — all failures return "—"
- Status emoji correct for all known statuses
- Date shown as YYYY-MM-DD (from created_at)
- Empty DB returns friendly message (not empty string)
- 18 tests, all green
