# Phase 3: CV Generation (Draft)

Generate a tailored CV for the candidate based on the JD analysis.
The candidate's full profile and experience are in your system context (PROFILE.md).

**This is a DRAFT — it will NOT be shown to the user. Phase 3.5 self-review runs next.**

---

## Input

User will provide:
1. JD text
2. JD_analysis.md content (Phase 1 + Phase 2 output)
3. Target language (English / Ukrainian / both)
4. Selected candidate name variant

---

## NON-NEGOTIABLE Rules

1. **NEVER copy-paste JD phrases verbatim** — absorb meaning, rewrite in natural language
2. **NEVER change actual job titles** — dishonest and verifiable
3. **NEVER fabricate experience** — if it doesn't exist, don't claim it
4. **NEVER remove a work experience entry** — every job in PROFILE.md stays in CV. Pre-2017 entries (SBC Distribution 2010–2014, Sole Proprietor 2008–2010, General Servers 2014–2015) omitted by default unless directly relevant
5. **CV language = input language** — English input → English CV; Ukrainian input → Ukrainian CV
6. **Do not self-apply "Senior"** unless officially held
7. **Avoid AI clichés** — "AI-Native", "AI-Driven mindset" etc.
8. **Avoid first-person pronouns** — standard CV convention
9. **"Built" implies coding** — use "Led design and delivery", "Owned", "Coordinated" for PM work
10. **Metrics belong in Key Results only** — do not duplicate in prose
11. **NO Skills section**
12. **NO Education section**
13. **NO Location**
14. **GitHub — include only if relevant** to this specific vacancy

---

## Language Precision

| Verb | When to use |
|------|------------|
| Owned | Responsible for product/outcome as PM |
| Led design and delivery | Drove product decisions, team executed |
| Coordinated | PM/coordinator role without full ownership |
| Built | Only if actually wrote code |
| Participated in | Contributed but didn't lead |

---

## CV Structure

```
[Selected Name]
[Headline]
[Email](mailto:alexeyibondarenko@gmail.com) · [Telegram](https://t.me/ioncat) · [LinkedIn](https://linkedin.com/in/alexibondarenko)
[GitHub](https://github.com/ioncat?tab=repositories)   ← only if relevant

SUMMARY
[2 paragraphs max. Full-arc positioning tailored to this vacancy.]
[AI tooling paragraph — include when vacancy has AI/product/digital signal; omit if vacancy is for AI product owner]

EXPERIENCE

[Role Title — exact as in employment records]
[Company | Dates]
[1–2 paragraphs: what was done, key decisions, context — tailored to this vacancy's pain]
Key results:
• [Metric/outcome]
• [Metric/outcome]

[...repeat for all roles, reverse chronological, default cutoff 2017...]

CERTIFICATIONS
Certified AI-Empowered SAFe® Product Owner/Product Manager
[Add AI certs only if vacancy explicitly focuses on AI product ownership]
```

**Headline options:**
- Default: `Product Owner / Product Manager`
- Adjust only if role archetype strongly differs (e.g. `Technical Program Manager`)

**AI Tooling Paragraph (standard text when applicable):**
> Applies AI tooling (Claude, ChatGPT) in practice — drafting requirements, synthesizing research, and pressure-testing product thinking before committing to direction. Practical understanding of how LLM inference pipeline design and data preparation stages affect output quality, developed through hands-on prototyping ([scheduling MVP](https://github.com/ioncat/dental-scheduling-mvp) — full PM artifact set · [LLM summarization pipeline](https://github.com/ioncat/yt-summarizer)).

---

## Tailoring Logic

Based on role archetype from Phase 1:
- Full PM (discovery + strategy + delivery) → lead with discovery + platform ownership
- Pure execution/delivery coordinator → lead with delivery track record
- Technical program management → lead with system complexity + cross-team coordination
- Operations/BizOps → lead with automation, process ownership, operational metrics

Emphasis = adjust language and which Key Results to surface first. Not deleting entries.

---

## Adaptation Plan Implementation

`JD_analysis.md` contains `## Adaptation Plan` from Phase 2. Implement ALL listed actions in this draft.

**Archetype mismatch handling** (if flagged in Phase 2 Key Barriers or Adaptation Plan):
- JD wants Founder Proxy → lead with SBC co-founder + Marketplace MVP 0→1; reframe HostiServer as "built from scratch" narrative; downplay InsulaLabs execution/coordination framing
- JD wants Executor → lead with HostiServer metrics track record; keep InsulaLabs; de-emphasize co-founder angle
- If not flagged → use default Tailoring Logic above

**Fit Breakdown ⚠️ items** (from Phase 2): where candidate has partial/pet-project evidence —
address by reframing existing experience. Do NOT fabricate. Do NOT claim ✅ if profile shows ⚠️.

**Fit Breakdown ❌ items**: do not mention, do not fabricate, do not imply.
