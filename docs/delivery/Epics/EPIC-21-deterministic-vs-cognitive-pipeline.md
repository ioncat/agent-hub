# EPIC-21 — Deterministic vs Cognitive pipeline split

**Status:** 📋 Planned
**Priority:** P0
**Last updated:** 2026-06-04
**Source:** `docs/discovery/hypotheses/H-002-pipeline-optimization-cognitive_vs_determined.md`

---

## Problem

The `/analyze` → cover pipeline is ~49 discrete actions. Only **~6 are cognitive** (Phase 1, 2, 3, 3.5, 4). The other **~43 are deterministic glue** (FS, DB, dedup, menu, mkdir, copy, cleanup, PDF render).

Two waste sources:

1. **Cognitive agent executes deterministic glue.** In local mode Claude Code (a reasoning agent) hand-clicks every mechanical step. Each glue step = an agent turn (read context → decide → tool-call → parse). The expensive thinking model does work an `if` should do.
2. **LLM does work that rules/code could do, inside cognitive phases.** Phase 3.5 currently asks the model to compute Top-15 word frequency, scan a tools registry, and detect repetition — all pure Python. Phase 1 extracts `Role — Company` and detects JD language — regex/lib jobs.

Plus: ad-hoc generative rendering is fragile. `services/pdf/render.py` `render_md()` is line-by-line parsing → two layout bugs surfaced in one session (cover overflow, contacts misparse).

Result: high latency (agent reasoning + redundant LLM), `Python→AI→Python→AI` flip-flops, unpredictable output.

---

## Goal

**Draw and enforce the boundary: deterministic work in Python, cognitive work in the LLM — called only where irreducible.**

- Deterministic skeleton = a Python orchestrator (FSM) that owns all I/O + rule/template/metric steps.
- LLM invoked only for the irreducible cognitive phases, as **single structured calls returning JSON** (not agentic multi-step loops).
- One skeleton, both modes: **API/headless** → orchestrator runs without an agent; **Local** → Claude Code calls the same scripts thinly instead of hand-doing steps.

---

## Local vs API reality (scope boundary)

| | Local (desktop Claude Code) | API / headless |
|---|---|---|
| Orchestrator | the agent (reasoning ALWAYS present) | Python (0 reasoning) |
| Glue (FS/DB/menu) | agent turns (can only be *thinned*) | pure code |
| LLM calls | agent itself = LLM | only on cognitive phases |
| Reasoning floor | **cannot be removed** | removed for glue |

**Consequence:** the full deterministic win lands in **API mode**. Local mode can only *thin* the agent (delegate to scripts), never zero its reasoning loop. The skeleton must be shared so local benefits too.

---

## Classification (H-002 framework applied)

### 🟢 Deterministic — Python, never AI
| Step | Mechanism |
|------|-----------|
| inbox scan, dedup (URL grep) | `scripts/inbox_scan.py` (done) |
| FS: mkdir / copy JD / write / cleanup | os/pathlib |
| DB: upsert / update / status / delete-inbox | `scripts/vacancy_track.py` (done) |
| mode / profile / user resolution | config + FSM |
| Step 0 menu, inbox menu rendering | string templates |
| **PDF render (CV + cover)** | **fixed template (Task 1)** |
| Quick Scan rendering | render from phase JSON |
| `Role — Company` extraction (1.0 header) | regex/parser |
| JD language detection (en/uk/ru) | `langdetect` / heuristic |
| Top-15 frequency check (3.5) | `collections.Counter` |
| Tools & Technologies scan (3.5) | dict match over registry |
| Repetition check (3.5) | n-gram frequency |

### 🔴 Cognitive — LLM (API or local), irreducible
| Phase | Why irreducible |
|-------|-----------------|
| Phase 1 — JD analysis | interpretation (pain, archetype, culture) |
| Phase 2 — fit assessment | judgment + barriers + adaptation reasoning |
| Phase 3 — CV draft | targeted generation |
| Phase 3.5 — self-review **verdict** | judgment what to cut/strengthen (metrics → Python; only the verdict stays LLM) |
| Phase 4 — cover | generation |

---

## Target architecture

```
Python orchestrator (FSM) — owns skeleton + all I/O + deterministic checks
   └─ calls LLM ONLY on cognitive phases, as single structured calls:
        call_1 → Phase 1+2  → JSON {analysis, fit, barriers, quick_scan...}
        call_2 → Phase 3+3.5 → JSON {cv_md, review}   (Top-15/tools/repetition computed in Python BEFORE the call, passed as context)
        call_3 → Phase 4    → {cover_md}
   └─ everything else (Quick Scan render, PDF, DB, files, menu) = Python
```

3 cognitive calls instead of a scatter of agent steps → kills `Python→AI→Python→AI` flip-flop.

---

## User Story

```
As the pipeline operator
I want deterministic steps run by Python and the LLM called only for genuine reasoning
So that the process is fast, predictable, cheap, and error-free — especially in API mode
```

---

## Acceptance Criteria

**Given** the pipeline runs end-to-end (analyze → CV → cover)
**When** a deterministic step executes (render, dedup, DB, metrics, title/lang)
**Then** it runs in Python with no LLM call

**Given** a cognitive phase runs
**When** the LLM is called
**Then** it is a single structured call returning JSON — no agentic multi-step loop for that phase

**Given** API/headless mode
**When** the full pipeline runs
**Then** no agent reasoning is spent on glue — only the 3 cognitive calls hit the model

**Given** CV or cover rendering
**When** PDF is produced
**Then** layout is identical every run, no overflow/misparse (fixed template)

---

## Tasks (blocker-ordered)

| # | Task | Severity | Depends on |
|---|------|----------|-----------|
| 1 | **Deterministic PDF templating** — CV-template + cover-template (HTML/Jinja2 + headless renderer, or structured fpdf2). Content slots in; no markdown line-shape guessing. Replaces `render_md`. | 🔴 BLOCKER | — |
| 2 | **Structured JSON contracts per cognitive phase** (Phase 1+2, Phase 3+3.5, Phase 4) — Pydantic models in `contracts/`. LLM returns JSON; orchestrator renders. | 🔴 BLOCKER | — |
| 3 | **Move deterministic metrics to Python** — Top-15 freq, Tools registry scan, repetition check, `Role — Company` extraction, JD language detection, Quick Scan render. | 🟠 | Task 2 |
| 4 | **Python orchestrator (FSM)** — drives the skeleton, calls LLM only on cognitive phases. Shared local + API. | 🟠 | Task 2 |
| 5 | **Merge cognitive calls** — Phase 1+2 = one call, Phase 3+3.5 = one call (metrics pre-computed, passed in). Reduce flip-flops. | 🟡 | Tasks 2, 4 |
| 6 | **Local mode delegates to orchestrator/scripts** — Claude Code calls scripts thinly instead of hand-doing glue. | 🟡 | Task 4 |
| 7 | **Measure latency + cost** before/after (per-phase timing already in ClaudeProvider; add orchestrator timing). | 🟢 | Tasks 4, 5 |

> **Task 1 = tomorrow's priority** (2026-06-05) and the cleanest "remove from AI contour" win. Independent of the rest — can land first.

---

## Top findings (H-002 deliverables)

**Top-5 remove from AI contour:** PDF render · Top-15 freq · Tools scan · repetition check · title-extraction + language-detection.
**Top-5 unjustified agent use (local):** the entire glue block (log steps 1–17, 20–23, 42–48) executed by a reasoning agent.
**Top latency sinks (keep AI, optimize):** Phase 3 CV generation · Phase 1+2 (extended thinking) · Phase 4 — optimize via single structured call, JSON output, PROFILE caching (done).

---

## Scope

### Code (new / changed)
| File | Change |
|------|--------|
| `services/pdf/` | template-based renderer (CV + cover templates) — Task 1 |
| `contracts/` | phase JSON models (analysis, fit, cv, review, cover) — Task 2 |
| `tools/` or `core/` | Python metrics module (freq, tools, repetition, title, lang) — Task 3 |
| `core/` | orchestrator FSM — Task 4 |
| `prompts/pm/`, `prompts/generic/` | phases emit JSON; drop in-prompt Top-15/tools/repetition instructions (moved to code) — Tasks 2,3 |
| `skill/SKILL.md`, `.claude/commands/analyze.md` | local mode delegates to orchestrator — Task 6 |

### Out of scope
- Onboarding interview (genuinely cognitive — stays LLM)
- Telegram/RSS surfaces beyond the shared skeleton
- Migrating existing `vacancies/` artifacts

---

## Dependencies
- EPIC-14 (services/pdf) — base renderer exists ✅ (Task 1 replaces its `render_md`)
- Today's fixes: `render_md` cover-aware, contacts standardized, docs → service-only (groundwork)

---

## Notes
- `H-002` workflow log is slightly stale: step 44 shows deprecated `cv_to_pdf.py` (removed 2026-06-04); steps 29–31 are one-off feedback edits, not pipeline.
- H-002 covers only the `/analyze` happy path — extend classification to onboarding/Telegram when those are touched.
