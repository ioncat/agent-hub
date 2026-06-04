# Phase 4: Cover Message

Write a short cover message tailored to this specific vacancy.
The candidate's full profile is in your system context (PROFILE.md).

**Cover language = vacancy language. English JD → English cover. Ukrainian JD → Ukrainian cover.**

---

## Input

User will provide:
1. JD text
2. Approved CV text (so cover aligns with CV framing)
3. JD_analysis.md content (Phase 1 + Phase 2 — for strongest match identification)

---

## Rules (NON-NEGOTIABLE)

- **Short** — greeting + body + closing line + name. Nothing more.
- **No formalism** — no "I am pleased to apply", no "Dear Hiring Manager", no narrative preamble
- **Focus on strengths only** — do NOT disclose gaps. Gaps are for interview, not cover.
- **Live, natural tone** — professional but human; not academic, not corporate
- **No copy-paste from JD** — rephrase their pain in natural language
- **Active verbs** — "managed", "owned", "coordinated" — not "management", "coordination"
- **Short bullets** — one clear fact per bullet, max 2 sentences. No nested clauses.
- **No narrative** — not "I find this role interesting because..." — show, don't explain interest
- **Closing line gender:** adapt to candidate (рада/радий — read from PROFILE.md context)

---

## Output Format — ALWAYS TWO VARIANTS SIDE-BY-SIDE

Generate **Варіант A** and **Варіант B** simultaneously. Display as two sections for direct comparison. User picks one (or requests a mix). Save only the approved version.

---

**ВАРІАНТ A — Narrative (short paragraphs)**
Concise, direct. Leads with tenure + role scope. Second paragraph: most relevant domain evidence. No bullets, no metrics. Natural professional tone.

**English template:**
```
Hi!

[1–2 sentences: years of experience + role scope relevant to this JD. Active verbs, no generic claims.]

[1 sentence: specific domain relevance — the strongest bridge between candidate's experience and JD focus.]

Happy to connect and learn more.

[Candidate name]
```

**Ukrainian template:**
```
Вітаю!

[1–2 sentences: years of experience + role scope relevant to this JD. Active verbs, no generic claims.]

[1 sentence: specific domain relevance.]

Буду рада поспілкуватися детальніше.

[Candidate name]
```

---

**ВАРІАНТ B — Bullets with evidence**
Evidence-heavy. Three specific bullets, each with a verifiable fact. Best for roles where structured proof matters.

**English template:**
```
Hi!

[1 sentence direct opener — no setup preamble]

- [Strongest match #1 — specific experience, active verbs, concrete fact]
- [Strongest match #2 — coordination/communication evidence, specific]
- [Strongest match #3 — concrete detail verifiable from profile]

[Specific closing referencing company/role — not generic "happy to chat"]

[Candidate name]
```

**Ukrainian template:**
```
Вітаю!

[1 sentence direct opener — no setup preamble]

- [Strongest match #1 — specific experience, active verbs, concrete fact]
- [Strongest match #2 — delivery/coordination evidence, specific]
- [Strongest match #3 — concrete detail verifiable from profile]

[Specific closing referencing company/role]

[Candidate name]
```

---

## Bullet Selection Logic

Pick 3 strongest matches based on Phase 1 + Phase 2 analysis:
- Bullet 1: strongest match to this role's primary pain or core requirement
- Bullet 2: complementary evidence — coordination, communication, or operational depth
- Bullet 3: most concrete and specific evidence from profile — tool, named outcome, or context

**Each bullet must be specific and verifiable from the profile — no generic claims.**
