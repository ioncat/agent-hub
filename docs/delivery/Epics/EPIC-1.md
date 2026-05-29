# Epic 1: knowledge-mirror-parser HTTP Endpoint

**Status:** 🔵 Planned
**Phase:** 1 — Core Infrastructure
**Priority:** 🔴 P0 — BLOCKER
**Blocks:** EPIC-2 (KMPAdapter), cv_fetch_jd tool, all CV pipeline

---

## Strategic Context

knowledge-mirror-parser currently has no HTTP interface — it's a CLI batch crawler. agent-hub needs to call it on demand for single URLs (job descriptions from Djinni/DOU). Running it as a separate HTTP service solves two problems at once: service autonomy (kmp stays independent) and async safety (kmp's sync `requests` + `time.sleep` run in their own process, never blocking agent-hub's event loop).

---

## Goal

knowledge-mirror-parser exposes a `POST /parse` endpoint. agent-hub sends a vacancy URL, gets back a `ParsedDocument` JSON object with clean Markdown. The rest of kmp internals stay untouched.

---

## Contract (defined here, implemented on both sides)

```python
# Request
{ "url": "https://djinni.co/jobs/123-product-manager/" }

# Response — ParsedDocument
{
  "title": "Product Manager at X",
  "markdown": "## About the role\n...",
  "source_url": "https://djinni.co/jobs/123-product-manager/"
}

# Errors
400  — missing or invalid URL
422  — URL validation failed
503  — target site unreachable or parse failed
```

---

## User Stories

### US-101: Parse single URL via HTTP

**Given** kmp-service is running
**When** agent-hub sends `POST /parse` with `{"url": "https://djinni.co/jobs/123/"}`
**Then** service returns `ParsedDocument` with non-empty `markdown` and correct `source_url`

**Notes for Engineering:**
- Endpoint calls existing `crawler.fetch(url)` → gets HTML response
- If URL matches a configured site_key (djinni, dou) → use `processor.process_article()` with that config
- If no matching site_key → fallback: `html2text` directly on raw HTML (generic extraction)
- `title`: extracted from `<h1>` or `<title>` tag
- `markdown`: cleaned body text, no navigation/footer garbage
- `source_url`: echo back the input URL

**Edge Cases:**
1. URL unreachable (network error) → 503 with `{"error": "fetch_failed", "detail": "..."}`
2. URL valid but page returns 404 → 503
3. URL is not a job page (wrong domain) → still parse, return what we get
4. Very long page (>100KB) → parse anyway, no truncation
5. Page with no `<h1>` → use `<title>` value or URL slug as title fallback

**Out of Scope:** authentication, pagination, PDF parsing, images in markdown

---

### US-102: Health check endpoint

**Given** kmp-service is running
**When** `GET /health` is called
**Then** returns `{"status": "ok"}` with HTTP 200

**Notes for Engineering:**
- Used by Docker Compose healthcheck
- No logic, just confirms service is alive

---

### US-103: Site configs for Djinni and DOU

**Given** a Djinni or DOU URL is passed to `POST /parse`
**When** service processes it
**Then** markdown contains job description body only — no nav, no sidebar, no footer, no "Apply" buttons

**Notes for Engineering:**
- Inspect Djinni job page HTML → find `content_selector` (main JD container)
- Inspect DOU job page HTML → same
- Add both to `config.py` as site configs
- `garbage_selectors`: navigation, header, footer, apply-button blocks, social links
- Can inspect HTML via: `curl -A "Mozilla/5.0" https://djinni.co/jobs/[id]/` or browser DevTools
- This US can be done in parallel with US-101 (different work)

**Edge Cases:**
1. Djinni job behind login → try without auth first, note if auth needed
2. DOU job page structure changes → site config may need update (not a blocker for MVP)

**Out of Scope:** login/cookies for paywalled content (Phase 2 if needed)

---

### US-104: Docker packaging

**Given** Docker Compose runs `docker compose up`
**When** kmp-service container starts
**Then** `GET /health` returns 200 within 30 seconds

**Notes for Engineering:**
- Add `Dockerfile` to knowledge-mirror-parser root:
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install -r requirements.txt
  COPY . .
  CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"]
  ```
- Add FastAPI + uvicorn to `requirements.txt`
- New file: `api.py` in kmp root — FastAPI app, imports from existing `crawler.py` + `processor.py`
- docker-compose.yml in agent-hub:
  ```yaml
  kmp-service:
    build: ../knowledge-mirror-parser
    ports:
      - "8001:8001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  ```
- `KMP_BASE_URL` env var in agent-hub config: `http://kmp-service:8001`

**Out of Scope:** HTTPS, auth tokens, rate limiting on kmp-service

---

## Implementation Plan

1. 🔴 **BLOCKER** Inspect Djinni + DOU HTML → determine `content_selector` and `garbage_selectors` for both sites. Add to `config.py`.
2. 🔴 **BLOCKER** Create `api.py` in knowledge-mirror-parser — FastAPI app with `POST /parse` + `GET /health`
3. 🟠 Add FastAPI + uvicorn to `requirements.txt`
4. 🟠 Add `Dockerfile` to knowledge-mirror-parser
5. 🟠 Add `kmp-service` to `docker-compose.yml` in agent-hub
6. 🟡 Manual test: `docker compose up kmp-service` → `curl POST /parse` with real Djinni URL → verify markdown output
7. 🟡 Create `contracts/parsed_document.py` in agent-hub (Pydantic model matching response)
8. 🟡 Create `adapters/kmp_adapter.py` in agent-hub (httpx wrapper)

---

## Open Questions

- [ ] Does Djinni require a logged-in session to see full JD? (needs manual check)
- [ ] Does DOU block automated requests without cookies? (needs manual check)
- [ ] Where does kmp SQLite DB live in Docker? (mount as volume or ephemeral per-request)

---

## Acceptance Criteria (Epic Level)

- `POST /parse` returns valid `ParsedDocument` for Djinni and DOU URLs
- Returned markdown contains job description text, no navigation/UI chrome
- `GET /health` returns 200
- Service runs in Docker via `docker compose up`
- agent-hub can call kmp-service via `KMPAdapter.fetch_markdown(url)` and get `ParsedDocument`
