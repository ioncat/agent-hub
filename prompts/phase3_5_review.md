# Phase 3.5: CV Self-Review

Review the generated CV draft against the specific vacancy. Identify what doesn't fit, what's weak, and what's missing.
The candidate's full profile is in your system context (PROFILE.md).

**Output language: Russian — always.**

This review is shown to the user BEFORE saving the CV. It is the first time the user sees the CV output.

---

## Input

User will provide:
1. JD text
2. JD_analysis.md content (Phase 1 + Phase 2)
3. The CV draft generated in Phase 3

---

## Questions to Answer for THIS Specific Vacancy

**What doesn't belong:**
- Which sections/paragraphs are NOT relevant to this role's actual pain?
- What experience is included out of habit but adds no signal here?
- What might mislead the reader — implying skills or experience that don't match the role?

**What's weak:**
- Which JD requirements are addressed too vaguely in the CV?
- Where is the language too generic when the JD uses specific terminology?
- What key pain point from Phase 1 analysis is NOT reflected in the CV?

**What's missing:**
- What relevant experience exists in the profile but wasn't highlighted?
- What framing would make existing experience map more clearly to this role?

---

## Output Format

```
CV SELF-REVIEW
—————————————
❌ Remove / doesn't fit:
• [item] — reason

⚠️ Weaken / compress:
• [item] — reason

🔧 Strengthen / reframe:
• [item] — what to change

✅ Strong — keep as is:
• [item]
```

Then output the updated CV draft with all identified changes already applied.

Separate the review from the CV with this exact line on its own:

```
---CV---
```

Do not use any other separator. The parser relies on `---CV---` to extract the CV.

---

## Phase 2 Implementation Check

Before the review output, verify three things from `JD_analysis.md`:

1. **Adaptation Plan** — list each action from Phase 2 `## Adaptation Plan`. Mark each:
   - ✅ applied in draft
   - ❌ not applied — add to 🔧 Strengthen / reframe

2. **Fit Breakdown ⚠️ items** — are bridgeable gaps addressed or reframed in the CV?
   If not → add to 🔧 Strengthen / reframe

3. **Fit Breakdown ❌ items** — are they properly absent (not fabricated or implied)?
   If any ❌ item appears in the draft → add to ❌ Remove / doesn't fit

---

## Rules

- If no issues in a category, write `• нет замечаний` — do not skip the category header
- Apply changes to the CV draft directly — do not output a separate diff
- Flag if AI tooling paragraph risks misleading for this specific role
- Flag if GitHub should be included or excluded for this specific role
- The self-review block will be appended to JD_analysis.md after user approval
