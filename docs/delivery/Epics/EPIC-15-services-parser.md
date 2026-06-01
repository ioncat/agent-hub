# EPIC-15 — services/parser/ — Own the job board parser

**Status:** 📋 Planned
**Phase:** Phase 3 of PIVOT-PLAN
**Priority:** P0 — Foundation
**Last updated:** 2026-06-01

---

## User Story

```
As a Career Agent developer
I want the job board parser to live inside the monorepo as a stripped, purpose-built service
So that the system has no external repo dependency for URL fetching and dead code from knowledge-mirror-parser is eliminated
```

---

## Acceptance Criteria

**Given** a Djinni or DOU vacancy URL
**When** `cv_fetch_jd` requests a parse
**Then** `KMPAdapter` hits `services/parser/` (internal) and returns clean Markdown — behaviour identical to external kmp-service

**Given** `docker compose up`
**When** all services start
**Then** `kmp-service` builds from `./services/parser/` — no reference to `../knowledge-mirror-parser`

**Given** the stripped service source
**When** counting files vs original knowledge-mirror-parser
**Then** ~60% of files are removed (database.py, processor.py, main.py, gopractice config, sitemap functions, login, download_binary)

---

## Edge Cases

- URL not matching known site configs → parser returns 404 / empty → `KMPAdapter` raises `ParseError`
- Site temporarily returns 429 / 503 → retry logic in `crawler.py` handles it (existing)

---

## Out of Scope

- New site configs (LinkedIn, HH.ru) — separate task
- Sitemap crawling — cut entirely
- WordPress auth — cut entirely

---

## Notes for Engineering

- Keep: `api.py` → `services/parser/app.py`, `crawler.py` (fetch/session/headers/delay only), `config.py` (djinni + dou only)
- Cut: `database.py`, `processor.py`, `main.py`, `discover_urls()`, `_parse_sitemap_xml()`, `login()`, `download_binary()`, gopractice config
- `KMPAdapter` unchanged — HTTP contract `POST /parse` stays identical
- `docker-compose.yml`: update build context `../knowledge-mirror-parser` → `./services/parser`

---

## Dependencies

- Independent of EPIC-13, 14

---

## Tasks

| # | Task | Status |
|---|------|--------|
| 1 | Copy + strip `crawler.py` → `services/parser/crawler.py` | 📋 |
| 2 | Copy + strip `config.py` → `services/parser/config.py` (djinni + dou only) | 📋 |
| 3 | Copy `api.py` → `services/parser/app.py` | 📋 |
| 4 | `services/parser/requirements.txt` + `Dockerfile` | 📋 |
| 5 | `docker-compose.yml` — update build context | 📋 |
| 6 | e2e verify: real DOU URL fetches via internal service | 📋 |
