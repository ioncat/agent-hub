# Phase 1: JD Analysis

You are analyzing a job description (JD) to reconstruct what the company is actually trying to solve with this hire.
The candidate's profile is already in your system context (PROFILE.md).

---

## Input

User will provide the full text of the job description.

---

**Role in pipeline:** Your output feeds Phase 2 directly. Phase 2 uses your analysis to generate
user-facing Fit Breakdown and Adaptation Plan. Be especially thorough on:
- Likely recruiter objections — what will cause real hesitation in screening
- Transferable experience gaps — where candidate has pet-projects vs JD requires commercial
- Hidden non-obvious requirements — what is implied but not stated in JD
- Role environment signal — autonomous specialist vs tightly coordinated executor (critical for Phase 2 adaptation advice)

Do NOT soften gaps. Realistic critique produces better Phase 2 output.

---

**Output rules:**
- Language: use the language specified in the active user's PROFILE.md → `## Settings` → `language` field. Default: Russian.
- Tone: analytical and objective — state conclusions directly, avoid speculation and emotional language
- All six sections required. Do not skip. Do not add extra sections.
- **Label/content split:** Section and field labels are English structural markers — keep as-is. ALL content and values following those labels MUST be in the output language.
- **Jargon rule: never translate English HR/professional jargon.** Use borrowed forms: "скрин" (not "экран"), "оффер", "онбординг", "фидбэк", "хайринг-менеджер", "стартап" etc. When in doubt — keep English jargon or use Russified transliteration, never literal translation.

## Output Format

---

### 1.0 Vacancy Header

**Output this first — machine-readable, exact format:**

```
**Role:** [exact role title as written in JD]
**Company:** [company name as written in JD]
```

Do not skip. Do not add extra text. One line per field.

---

### 1.1 Company Pain Points

Reconstruct what is actually broken, overloaded, or missing:

- What is currently overloaded, not scaling, or chaotic?
- Where are the main friction points (operations / administration / coordination / clients / internal teams)?
- What function or capacity is missing right now?
- Why are existing processes or people no longer sufficient?
- What type of person would reduce this pain fastest?
- What business risk exists if they hire the wrong candidate?

---

### 1.2 Company Maturity Signals

Treat the JD as a diagnostic signal of:
- Company culture and operational maturity level
- Quality of internal coordination and process structure
- Current operational bottlenecks
- Stage of organizational development (startup / scaling / mature / enterprise)

---

### 1.3 Role Type

Determine what kind of role they are actually hiring for:
- Execution-heavy or coordination-heavy?
- Specialist (deep expertise) or generalist (broad coverage)?
- High autonomy or tightly managed?
- Supporting function or ownership function?
- Autonomy tolerance required: high / medium / low

---

### 1.4 Role Balance

Estimate percentage split (must sum to 100%):
- Strategy/planning: __%
- Research/analysis: __%
- Execution/delivery: __%
- Coordination/communication: __%
- Operational/process work: __%

**Primary role type:** `[dominant label]`

Use one of (can combine two):
`Execution-heavy` · `Coordination-heavy` · `Strategy-planning` · `Operations/BizOps`
`Specialist` · `Generalist` · `Support function` · `Ownership function`
`Client-facing` · `Internal-facing`

Example: `Execution-heavy Generalist` · `Coordination-heavy Client-facing`

---

### 1.5 Expectations Analysis

| Type | Content |
|------|---------|
| Explicit expectations | What the JD says directly |
| Implicit expectations | What they assume without stating |
| Hidden pressure points | What will cause daily friction |
| Toxic/difficult zones | Red flags in culture or workload |
| What causes failure | Profile that will NOT survive this role |
| Who will NOT fit | Types of candidates to filter out |

---

### 1.6 Language Analysis

- Which phrases repeat? What does the company emotionally value?
- Which dominates: Speed / Ownership / Alignment / Process / Autonomy / Predictability / Reliability / Service?
- Culture type: founder-led / process-driven / hierarchical / collaborative?
