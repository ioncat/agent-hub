# EPIC-14 — services/pdf/ — Kill subprocess PDF dependency

**Status:** ✅ Done (2026-06-01)
**Phase:** Phase 2 of PIVOT-PLAN
**Priority:** P0 — Foundation
**Last updated:** 2026-06-01

---

## User Story

```
As a Career Agent developer
I want PDF generation to run as an internal HTTP service
So that the system has no subprocess dependency on an external repo (callback-cv) and PDF rendering is independently deployable and testable
```

---

## Acceptance Criteria

**Given** a CV in Markdown format
**When** `cv_generate` requests a PDF
**Then** `CVAdapter` sends `POST /render` to `pdf-service` and receives PDF bytes — no subprocess call

**Given** `pdf-service` is down
**When** `cv_generate` requests a PDF
**Then** `CVAdapter` raises a typed error; user receives an error message; no silent fallback

**Given** `docker compose up`
**When** all services start
**Then** `pdf-service` starts from `./services/pdf/` build context — no reference to `../callback-cv`

**Given** the same Markdown input
**When** PDF is generated via HTTP vs old subprocess
**Then** output PDF is visually identical (same renderer, same fonts)

---

## Edge Cases

- `pdf-service` returns non-200 → `CVAdapter` raises `PDFRenderError` with status + body
- Markdown contains unsupported characters (e.g. `●` dot-bar) → service returns error, not crash
- Large CV (>10k tokens rendered) → service handles without timeout at default 30s

---

## Out of Scope

- HTML template system (separate decision — BACKLOG P1)
- Multi-language PDF variants
- `CVAdapter` streaming response

---

## Notes for Engineering

- Extract from `callback-cv/cv_to_pdf.py`: `md_to_pdf()`, `CVDocument`, `render_md()` — ~260 lines
- Fonts (`Segoe UI` ttf) move to `services/pdf/fonts/`
- FastAPI endpoint: `POST /render` — body `{"markdown": str}` → response `application/pdf`
- `CVAdapter` switches `subprocess.run(...)` → `httpx.post(settings.pdf_service_url, ...)`
- `core/settings.py`: add `PDF_SERVICE_URL`, remove `CALLBACK_CV_PATH`
- `docker-compose.yml`: add `pdf-service` container, build from `./services/pdf/`
- Tools layer (`cv_generate.py`, `cv_cover.py`) unchanged

---

## Dependencies

- No hard dependency on EPIC-13, but deploy together for clean monorepo state

---

## Tasks

| # | Task | Status |
|---|------|--------|
| 1 | `services/pdf/render.py` — extracted rendering core | ✅ Done |
| 2 | `services/pdf/app.py` — FastAPI `POST /render` | ✅ Done |
| 3 | `services/pdf/fonts/` — Segoe UI fonts | ✅ Done |
| 4 | `services/pdf/requirements.txt` + `Dockerfile` | ✅ Done |
| 5 | `adapters/cv_adapter.py` — subprocess → httpx | ✅ Done |
| 6 | `core/settings.py` — add `PDF_SERVICE_URL`, remove `CALLBACK_CV_PATH` | ✅ Done |
| 7 | `docker-compose.yml` — add `pdf-service` | ✅ Done |
| 8 | `tests/test_cv_adapter.py` — mock httpx, verify PDF response handling | ✅ Done |
