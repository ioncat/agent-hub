# Onboarding Interview — Generic / Other Roles

> **STATUS: 🔴 STUB — AI Interview System not yet designed.**
> This file is a placeholder. Full design required before implementation.
> See: `docs/discovery/core-differentiators.md` — AI Interview System.

---

## When this file will be used

Called by `tools/cv_onboard.py` during onboarding Phase 2 (Interview).
Used when `skill_type = 'generic'` — for non-PM roles.

Input to the LLM:
- Candidate's parsed CV text (from PDF)
- This prompt as the system instruction

Expected LLM output:
- 5–8 personalised questions based on the candidate's background
- Questions should surface: domain expertise, impact evidence, scope of responsibility

---

## Design constraints (to resolve before implementation)

- Same evidence-based approach as PM version, but role-agnostic
- Must be adaptable to wide range of roles (Engineering, Design, Marketing, etc.)
- Output must be parseable into the shared structured profile JSON schema (schema TBD)

---

## Placeholder system prompt (DO NOT USE IN PRODUCTION)

You are a career counsellor. You have received a candidate's CV.
Conduct a focused interview to build a rich profile of their experience.

Ask 5–8 targeted questions grounded in their specific CV.
Focus on: measurable impact, scope of work, decision-making authority, key achievements.

<!-- REPLACE THIS WITH PRODUCTION PROMPT AFTER DESIGN REVIEW -->
