# Epic 8: CV Analysis Tool

**Status:** 🟢 Done
**Phase:** 2 — CV Pipeline
**Priority:** 🟡 P2
**Blocks:** EPIC-9 (cv_generate)

---

## Strategic Context

Second pipeline step. Takes a fetched vacancy (JD.md on disk + DB row) and runs two-phase
Claude analysis: structural JD analysis (Phase 1) then candidate fit assessment (Phase 2).
Output is `JD_analysis.md` in the vacancy folder, with a Quick Scan block sent to Telegram.

PROFILE.md is always the cached system block via `ClaudeProvider` — established in EPIC-3.
Prompts are loaded from `prompts/` files — established in EPIC-6.

---

## Goal

`tools/cv_analyze.py` exposes `cv_analyze(ctx, vacancy_id) → str`.
Registered in `agent.py` ToolRegistry. Called when the router detects an analyze intent.

---

## Phases

| Phase | Prompt file | User input | Output |
|-------|-------------|------------|--------|
| Phase 1 | `phase1_analysis.md` | JD text | Structural JD analysis (6 sections) |
| Phase 2 | `phase2_fit.md` | JD text + Phase 1 output | Fit dimensions + Quick Scan block |

Phase 2 user message concatenation:
```
{jd_text}

---

Phase 1 Analysis:

{phase1_output}
```

---

## File Layout

```
vacancies/{site}/YYYY-MM/{slug}/
├── JD.md                 ← written by EPIC-7
└── JD_analysis.md        ← written by this tool
```

### JD_analysis.md structure

```markdown
# Analysis: {title}

Source: {url}
Date: YYYY-MM-DD

---

## Quick Scan
...

---

## Phase 2: Candidate Fit Assessment
...

---

## Phase 1: JD Analysis
...
```

---

## User Stories

### US-801: Analyze fetched vacancy

**Given** user asks to analyze vacancy 42
**When** `cv_analyze(ctx, 42)` runs
**Then**:
- Phase 1 prompt + JD text → Claude → phase1 output
- Phase 2 prompt + JD + phase1 → Claude → phase2 output with Quick Scan
- `JD_analysis.md` written to vacancy folder (Quick Scan at top)
- `pipeline_runs` rows inserted for phase1 + phase2
- Vacancy status updated to `analyzed`
- Telegram reply: "✅ Анализ готов" + Quick Scan block

### US-802: Vacancy not in DB

**Given** `vacancy_id` not found in SQLite
**When** `cv_analyze` runs
**Then** return user-friendly error "⚠️ Вакансия #N не найдена в базе"

### US-803: JD.md missing from disk

**Given** DB row exists but file was deleted
**When** `cv_analyze` runs
**Then** return user-friendly error with file path

### US-804: Claude unavailable on Phase 1

**Given** Claude returns `LLMError` on Phase 1 call
**When** `cv_analyze` runs
**Then**:
- `pipeline_runs` row for phase1 marked `error`
- `update_vacancy_status` NOT called
- `JD_analysis.md` NOT written
- User-friendly error returned

### US-805: Claude unavailable on Phase 2

**Given** Phase 1 succeeds, Phase 2 raises `LLMError`
**When** `cv_analyze` runs
**Then**:
- `pipeline_runs` row for phase2 marked `error`
- `update_vacancy_status` NOT called
- `JD_analysis.md` NOT written (no partial output)
- User-friendly error returned

---

## Implementation Plan

1. 🔴 `tools/cv_analyze.py` — tool function + `_extract_quick_scan` + `_build_analysis_file`
2. 🔴 Update `agent.py` — register `cv_analyze` in `_register_tools`
3. 🟠 `tests/test_cv_analyze.py` — mock LLM + DB + filesystem

---

## Acceptance Criteria

- Phase 1 called with JD text as user, `phase1_analysis.md` as system
- Phase 2 called with JD + Phase 1 output as user, `phase2_fit.md` as system
- `JD_analysis.md` saved in correct vacancy folder (same dir as JD.md)
- `pipeline_runs` rows: phase1 + phase2, correct status transitions
- Vacancy status → `analyzed`
- Quick Scan block extracted from Phase 2 output and sent to Telegram
- LLM error → user-friendly message, no partial file written, status not updated
