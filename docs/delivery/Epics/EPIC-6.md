# Epic 6: Prompt Files

**Status:** 🟢 Done
**Phase:** 2 — CV Pipeline
**Priority:** 🔴 P0 — BLOCKER
**Blocks:** EPIC-8 (cv_analyze), EPIC-9 (cv_generate), EPIC-10 (cv_cover)

---

## Strategic Context

Phase prompts extracted from `callback-cv/skill/SKILL.md` into standalone Markdown files.
Each file is loaded by its CV tool and passed as `system=` to `ClaudeProvider.complete()`.
PROFILE.md is always in the cached system block — prompts do not repeat profile data.

Call structure per LLM request:
```
System block 1 (cached): PROFILE.md content
System block 2 (task):   prompts/phaseX.md content
User turn:                JD text / previous phase output / CV draft
```

---

## Files

| File | Used by | Input (user turn) | Output |
|------|---------|-------------------|--------|
| `prompts/phase1_analysis.md` | cv_analyze.py | JD text | Phase 1 analysis (RU) |
| `prompts/phase2_fit.md` | cv_analyze.py | JD text + Phase 1 output | Fit table + summary (RU) |
| `prompts/phase3_cv_draft.md` | cv_generate.py | JD_analysis.md + name + language | CV in Markdown |
| `prompts/phase3_5_review.md` | cv_generate.py | CV draft + JD text | Self-review block |
| `prompts/phase4_cover.md` | cv_cover.py | JD text + CV text | Cover message |

---

## Acceptance Criteria

- All 5 prompt files exist in `prompts/`
- Each file is self-contained — no references to other prompt files
- Prompts do not duplicate PROFILE.md content (it's in cached system block)
- Output format specs are unambiguous (headers, tables, bullet format)
