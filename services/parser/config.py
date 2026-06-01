"""
config.py — Job board site configurations for career-agent parser service.

Stripped from knowledge-mirror-parser: only djinni.co + jobs.dou.ua retained.
Sitemap config, batch processing, and knowledge-mirror sites removed.
"""

# ── Scraper safety settings ───────────────────────────────────────────────────

REQUEST_DELAY_RANGE = (2, 5)   # seconds (min, max)
MAX_RETRIES = 3
RETRY_BACKOFF = 2              # exponential back-off multiplier

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]

# ── Job board site configs ────────────────────────────────────────────────────

SITES: dict = {
    "djinni.co": {
        "base_url": "https://djinni.co",
        "content_selector": ".job-post__description",
        "garbage_selectors": [
            "nav",
            "header",
            ".site-footer",
            ".fixed-bottom",
            ".modal-content",
            ".salaries-info-link",
            "script",
            "style",
            "iframe",
        ],
    },

    "jobs.dou.ua": {
        "base_url": "https://jobs.dou.ua",
        "content_selector": ".b-typo.vacancy-section",
        "garbage_selectors": [
            ".b-content-menu",
            ".b-jobs-search",
            ".b-dou-vacancies",
            "nav",
            "header",
            "footer",
            "script",
            "style",
            "iframe",
        ],
    },
}


def get_site_cfg(site_key: str) -> dict:
    """Return config for a site key. Raises KeyError if unknown."""
    if site_key not in SITES:
        raise KeyError(f"No configuration for site: {site_key!r}")
    return SITES[site_key]
