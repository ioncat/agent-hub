"""
crawler.py — Polite HTTP fetching for job board URLs.

Stripped from knowledge-mirror-parser: sitemap discovery, WordPress login,
asset downloader, and batch processing removed. Only fetch() retained.
"""

import logging
import random
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, ReadTimeout, Timeout
from urllib3.util.retry import Retry

from config import MAX_RETRIES, REQUEST_DELAY_RANGE, RETRY_BACKOFF, USER_AGENTS

log = logging.getLogger(__name__)


# ── HTTP session ──────────────────────────────────────────────────────────────

def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_session: requests.Session = _build_session()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _random_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.7,en;q=0.5",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "DNT": "1",
    }


def _polite_delay() -> None:
    delay = random.uniform(*REQUEST_DELAY_RANGE)
    log.debug("Polite delay: %.1f s", delay)
    time.sleep(delay)


# ── Core fetch ────────────────────────────────────────────────────────────────

def fetch(url: str) -> Optional[requests.Response]:
    """Fetch *url* with polite delay and retry logic.

    Returns Response on success, None on failure.
    """
    _polite_delay()
    attempt = 0
    while attempt <= MAX_RETRIES:
        try:
            resp = _session.get(
                url,
                headers=_random_headers(),
                timeout=(10, 30),
                allow_redirects=True,
            )
            resp.raise_for_status()
            log.info("[%d] %s", resp.status_code, url)
            return resp

        except ReadTimeout:
            attempt += 1
            wait = RETRY_BACKOFF ** attempt
            log.warning("Read timeout on %s (attempt %d/%d) — retrying in %.0fs",
                        url, attempt, MAX_RETRIES, wait)
            if attempt > MAX_RETRIES:
                break
            time.sleep(wait)

        except (ConnectionError, Timeout) as exc:
            attempt += 1
            wait = RETRY_BACKOFF ** attempt
            log.warning("Connection error on %s (attempt %d/%d): %s — retrying in %.0fs",
                        url, attempt, MAX_RETRIES, exc, wait)
            if attempt > MAX_RETRIES:
                break
            time.sleep(wait)

        except requests.RequestException as exc:
            log.warning("Request failed for %s: %s", url, exc)
            break

    log.error("Giving up on %s after %d attempts", url, attempt)
    return None
