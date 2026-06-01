# EPIC-17 — Onboarding: PDF → Interview → Profile

**Status:** 📋 Planned
**Phase:** Phase 5 of PIVOT-PLAN
**Priority:** P0 — Foundation
**Last updated:** 2026-06-01

---

## User Story

```
As a job seeker
I want to upload my CV and answer a few questions in Telegram
So that Career Agent builds a rich, personalised profile for me automatically — without editing any files
```

---

## Acceptance Criteria

**Given** a new user sends `/start`
**When** the onboarding flow begins
**Then** the bot asks: target role type (PM / other), name, and requests CV PDF upload

**Given** the user uploads a PDF
**When** the PDF is received
**Then** it is converted to Markdown and the LLM generates a personalised interview based on the candidate's background

**Given** the LLM generates an interview
**When** the user answers questions in Telegram
**Then** the bot conducts a multi-turn conversation; LLM extracts experience depth

**Given** the interview is complete
**When** the LLM synthesises the transcript
**Then** a structured profile is stored in the DB per user and used for all future pipeline runs

**Given** a user runs `/update_profile`
**When** the command is received
**Then** the re-interview flow starts; existing profile is enriched, not replaced

**Given** the profile is stored in DB
**When** `ClaudeProvider` loads the system prompt
**Then** profile text comes from DB — `PROFILE.md` file is no longer required

---

## Edge Cases

- PDF parsing fails (scanned image, password-protected) → user notified, asked to upload text-based PDF or paste text manually
- User abandons onboarding mid-flow → partial state saved; `/start` resumes from last step
- `skill_type` answer not in known list → default to `'generic'`, notify user
- Profile too long for single cache block → truncate to fit within cache limit, log warning

---

## Out of Scope

- Voice message → transcript (separate tool, Phase 4 extensions)
- LinkedIn import
- Profile versioning / history

---

## Notes for Engineering

- PDF → Markdown: `pypdf` or `pdfminer.six` (prefer `pypdf` — lighter)
- Interview prompts: separate prompt files per `skill_type` — `prompts/pm/onboarding_interview.md`, `prompts/generic/onboarding_interview.md`
- Multi-turn state: FSM in Telegram handler (aiogram FSMContext) or simple DB flag per user (`onboarding_step`)
- Profile storage: JSON field in `users.profile_json` OR separate `profiles` table — decision at implementation time
- `core/llm_client.py`: `ClaudeProvider` loads profile from DB; `PROFILE_MD_PATH` removed from settings
- `/set_skill` command: updates `users.skill_type` in DB; takes effect on next pipeline run

---

## Dependencies

- EPIC-13 (user_id in DB) — required
- EPIC-14 (services/pdf/) — optional at start; fallback to subprocess until EPIC-14 done

---

## Tasks

| # | Task | Status |
|---|------|--------|
| 1 | Telegram `/start` flow + `skill_type` question | 📋 |
| 2 | PDF upload handler + Markdown extraction (`pypdf`) | 📋 |
| 3 | LLM interview generation prompt (`prompts/[skill_type]/onboarding_interview.md`) | 📋 |
| 4 | Multi-turn conversation FSM (aiogram FSMContext) | 📋 |
| 5 | Profile synthesis: transcript → structured profile → DB | 📋 |
| 6 | `ClaudeProvider` loads profile from DB instead of file | 📋 |
| 7 | `/update_profile` command — re-interview flow | 📋 |
| 8 | `/set_skill` command — updates `users.skill_type` | 📋 |
| 9 | Remove `PROFILE_MD_PATH` from settings | 📋 |
