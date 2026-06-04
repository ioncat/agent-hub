# EPIC-20 — Unified vacancy path standard

**Status:** 🔄 In Progress (Tasks 3,4,5 done; Tasks 1,2,6 pending)
**Priority:** P1
**Last updated:** 2026-06-02

---

## Problem

Two pipelines write to `vacancies/` with different path schemas:

| Pipeline | Current path | Standard |
|----------|-------------|----------|
| Local skill (`/analyze`) | `vacancies/[Company — Role]/` | ❌ no user_id |
| Telegram bot (`cv_fetch_jd`) | `vacancies/{user_id}/{site}/{YYYY-MM}/{slug}/` | ❌ not human-readable, no company name |

Neither matches the agreed standard. Multi-user filtering in tracker and analytics is broken.

---

## Goal

**One path standard, everywhere:**

```
vacancies/{user_id}/{Company — Role}/
```

Examples:
```
vacancies/001/Alliance Digital — Product Manager/
vacancies/001/Stripe — Senior PM/
vacancies/002/Google — Product Lead/
```

- `user_id` = zero-padded string (`001`, `002`, ...) — from DB or `skill/active_user`
- `Company — Role` = human-readable name, em dash separator

---

## User Story

```
As the web tracker / analytics layer
I want all vacancy artifacts grouped by user_id and labeled with company+role
So that I can filter, display, and query vacancies per user without touching the DB
```

---

## Acceptance Criteria

**Given** any pipeline creates a vacancy (Telegram or local skill)
**When** artifacts are saved
**Then** path is `vacancies/{user_id}/{Company} — {Role}/`

**Given** an inbox_manual file is processed
**When** pipeline finishes
**Then** artifacts go to `vacancies/{user_id}/{Company} — {Role}/` — not to root vacancies/

**Given** the web tracker lists vacancies
**When** filtering by user
**Then** it can use filesystem path as the source of truth (no DB required for basic listing)

---

## Blockers

### `ParsedDocument` missing `company` field

`contracts/parsed_document.py` currently has only `title`, `markdown`, `source_url`.

`cv_fetch_jd.py` builds path from URL slug — no company name available at fetch time.

**Fix needed:**
1. Add `company: str` to `ParsedDocument`
2. Update `services/parser/` to extract company name from JD page (header / "About company" section)
3. `cv_fetch_jd.py` line 77: change path construction:
   ```python
   # Before:
   vacancy_dir = ctx.deps.vacancies_path / str(ctx.deps.user_id) / site / month / slug
   # After:
   folder_name = f"{doc.company} — {doc.title}" if doc.company else doc.title
   vacancy_dir = ctx.deps.vacancies_path / str(ctx.deps.user_id) / folder_name
   ```

---

## Scope

### Code changes

| File | Change |
|------|--------|
| `contracts/parsed_document.py` | Add `company: str` field |
| `services/parser/app.py` | Extract company from page, populate `company` |
| `tools/cv_fetch_jd.py` | Line 77: new path construction |
| `tests/test_cv_fetch_jd.py` | Update path assertions |

### Already done (local skill — docs only)
- `skill/SKILL.md` — path rule updated to `vacancies/[user_id]/[Company — Role]/`
- `.claude/commands/analyze.md` — same
- `docs/local-app.md` — same
- `docs/system-flow.md` — same

### Out of scope
- Migrating existing `vacancies/` folders on disk (local artifacts, gitignored)
- DB `markdown_path` column migration (update as vacancies are re-processed)

---

## Dependencies

- EPIC-15 (services/parser/) — must be running to test company extraction
- EPIC-13 (user_id in AgentDeps) — already done ✅

---

## Tasks

| # | Task | Status |
|---|------|--------|
| 1 | Add `company: str` to `ParsedDocument` | 📋 |
| 2 | Parser: extract company from JD page | 📋 |
| 3 | `cv_fetch_jd.py`: new path construction (`inbox/{user_id}/{slug}/`) | ✅ Done (2026-06-02) |
| 4 | Update tests: path assertions | ✅ Done (2026-06-02) |
| 5 | After Phase 1 analysis: update DB `title` to `Role — Company` format | ✅ Done (2026-06-02) |
| 6 | Verify: end-to-end fetch → correct folder, correct title in tracker | 📋 |

---

## Folder standard (updated 2026-06-02)

Agreed structure after discussion:

```
vacancies/
├── inbox/              ← все вакансии (авто + мануал после обработки)
│   └── {user_id}/
│       └── {Role — Company}/   ← финальное место
│           ├── JD.md
│           ├── JD_analysis.md
│           ├── {Full Name}_CV.md
│           └── ...
└── inbox_manual/       ← стейджинг для ручного дропа; очищается после обработки
    └── {Role — Company}/
```

- `processed/` в inbox_manual убрана — после обработки файл переезжает в `inbox/{user_id}/`
- Telegram pipeline пишет в `inbox/{user_id}/{slug}/JD.md` → после Phase 1 `title` обновляется в DB (`Role — Company`)
- DB = mapping table: `markdown_path` содержит slug-путь, `title` содержит human-readable имя
