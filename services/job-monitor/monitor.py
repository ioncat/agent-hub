"""
Job vacancy monitor — multi-feed, multi-user
Each feed sends to its own list of Telegram chat IDs.

Usage:
    python monitor.py                # check every 5 minutes
    python monitor.py --interval 10  # check every 10 minutes
    python monitor.py --once         # single check and exit
    python monitor.py --debug        # show feed contents, no notifications
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

import aiohttp

_BASE = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent)))
_PROJECT = Path(__file__).parent
LOG_FILE = _BASE / "monitor.log"
STATE_FILE = _BASE / "seen_jobs.json"
LOCK_FILE = _BASE / "monitor.lock"
FEEDS_FILE = _PROJECT / "feeds.json"
CONFIG_FILE = _PROJECT / "config.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (vacancy-monitor/1.0)"}

# Defaults applied when config.json is missing or a field is omitted.
# apply_config() overrides these module globals at startup.
DEFAULT_CONFIG = {
    "interval_minutes": 5,
    "http_timeout": {"total_seconds": 30, "connect_seconds": 10},
    "check_timeout_seconds": 120,
    "retry": {"backoff_schedule_seconds": [60, 300, 1800, 7200]},
    "telegram": {"disable_web_page_preview": False},
    "logging": {"level": "INFO", "max_bytes": 10 * 1024 * 1024, "backup_count": 5},
}

# Mutable module globals — set by apply_config() in main() before async_main runs.
# These are read by check(), retry_pending(), send_telegram() etc.
HTTP_TIMEOUT = aiohttp.ClientTimeout(
    total=DEFAULT_CONFIG["http_timeout"]["total_seconds"],
    connect=DEFAULT_CONFIG["http_timeout"]["connect_seconds"],
    sock_connect=DEFAULT_CONFIG["http_timeout"]["connect_seconds"],
    sock_read=DEFAULT_CONFIG["http_timeout"]["total_seconds"],
)
BACKOFF_SCHEDULE = list(DEFAULT_CONFIG["retry"]["backoff_schedule_seconds"])
MAX_ATTEMPTS = len(BACKOFF_SCHEDULE) + 1
DISABLE_WEB_PAGE_PREVIEW = DEFAULT_CONFIG["telegram"]["disable_web_page_preview"]
CHECK_TIMEOUT: int = DEFAULT_CONFIG["check_timeout_seconds"]

# Salary extraction. DOU embeds salary directly in <title> when present (e.g.
# "Business Analyst в DevCom, $1500–2000, Львів, віддалено" or "...до $1700").
# Matches: $1500, $1500-2000, $1500–2000, $1500—2000. Optional whitespace around
# numbers and dash. Captures the entire match so we can show it verbatim.
SALARY_RE = re.compile(r"\$\s*\d{1,5}(?:\s*[–—\-]\s*\d{1,5})?")


def acquire_lock() -> None:
    """Exit if another instance is already running."""
    if LOCK_FILE.exists():
        pid = LOCK_FILE.read_text().strip()
        # check if that pid is actually alive
        try:
            import psutil
            if psutil.pid_exists(int(pid)):
                print(f"ERROR: another instance already running (PID {pid}). Exiting.")
                sys.exit(1)
        except ImportError:
            # psutil not available — fall back to just checking the file
            print(f"ERROR: lock file exists (PID {pid}). If no other instance runs, delete monitor.lock and retry.")
            sys.exit(1)
    LOCK_FILE.write_text(str(os.getpid()))


def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def setup_logging(level: str = "INFO", max_bytes: int = 10 * 1024 * 1024,
                  backup_count: int = 5) -> None:
    """Wire stdout + a rotating monitor.log handler. Rotation keeps the
    log file from growing unbounded between restarts."""
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[file_handler, stream_handler],
        force=True,  # replace any pre-existing handlers (re-config-safe)
    )


log = logging.getLogger(__name__)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursive dict merge — override wins, nested dicts are merged not replaced."""
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> dict:
    """Read config.json layered on top of DEFAULT_CONFIG. Missing file or
    invalid JSON → pure defaults (warning to stderr; logging not up yet)."""
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    try:
        user = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        sys.stderr.write(f"WARNING: {CONFIG_FILE.name} invalid ({e}) — using defaults\n")
        return dict(DEFAULT_CONFIG)
    if not isinstance(user, dict):
        sys.stderr.write(f"WARNING: {CONFIG_FILE.name} must be a JSON object — using defaults\n")
        return dict(DEFAULT_CONFIG)
    return _deep_merge(DEFAULT_CONFIG, user)


def apply_config(config: dict) -> None:
    """Push validated config into module globals consumed by async code paths."""
    global HTTP_TIMEOUT, BACKOFF_SCHEDULE, MAX_ATTEMPTS, DISABLE_WEB_PAGE_PREVIEW, CHECK_TIMEOUT
    ht = config["http_timeout"]
    HTTP_TIMEOUT = aiohttp.ClientTimeout(
        total=ht["total_seconds"],
        connect=ht["connect_seconds"],
        sock_connect=ht["connect_seconds"],
        sock_read=ht["total_seconds"],
    )
    BACKOFF_SCHEDULE = list(config["retry"]["backoff_schedule_seconds"])
    MAX_ATTEMPTS = len(BACKOFF_SCHEDULE) + 1
    DISABLE_WEB_PAGE_PREVIEW = bool(config["telegram"]["disable_web_page_preview"])
    CHECK_TIMEOUT = int(config.get("check_timeout_seconds", 120))


def load_feeds() -> list[dict]:
    """Read feeds.json and resolve recipient labels (e.g. CHAT_ID_1) to actual
    chat IDs via os.environ. Exits with a helpful error on misconfiguration."""
    if not FEEDS_FILE.exists():
        log.error(
            "%s missing. Copy feeds.example.json to feeds.json and edit it "
            "with your own feed URLs and recipient labels.", FEEDS_FILE.name
        )
        sys.exit(1)
    try:
        raw = json.loads(FEEDS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.error("%s invalid JSON: %s", FEEDS_FILE.name, e)
        sys.exit(1)
    if not isinstance(raw, list) or not raw:
        log.error("%s must be a non-empty JSON array", FEEDS_FILE.name)
        sys.exit(1)
    feeds = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            log.error("%s entry %d must be a JSON object", FEEDS_FILE.name, i)
            sys.exit(1)
        for field in ("name", "url", "recipients"):
            if field not in entry:
                log.error("%s entry %d missing required field '%s'",
                          FEEDS_FILE.name, i, field)
                sys.exit(1)
        if not isinstance(entry["recipients"], list) or not entry["recipients"]:
            log.error("%s entry %r: 'recipients' must be a non-empty list",
                      FEEDS_FILE.name, entry["name"])
            sys.exit(1)
        resolved = []
        for label in entry["recipients"]:
            chat_id = os.environ.get(label)
            if not chat_id:
                log.error(
                    "%s entry %r references %s but .env has no such variable",
                    FEEDS_FILE.name, entry["name"], label
                )
                sys.exit(1)
            resolved.append(chat_id)
        feeds.append({"name": entry["name"], "url": entry["url"], "recipients": resolved})
    return feeds


def load_env() -> str:
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())
    return os.environ.get("TELEGRAM_TOKEN", "")


# State format (per-recipient delivery, IPN-style):
# {
#   "https://jobs.example.com/123": {
#     "title": "Senior PM",
#     "feed": "DOU.ua — Product Manager",
#     "first_seen": "2026-05-14T14:41:13",
#     "delivery": {
#       "111111111": {
#         "status": "sent" | "pending" | "failed",
#         "attempts": 0,
#         "last_attempt": "2026-05-14T14:41:13" | null,
#         "last_error": "..." | null
#       },
#       ...
#     }
#   }
# }
#
# Idempotency unit: (job_link, chat_id). A successful "sent" status is never
# retried. A "failed" status (MAX_ATTEMPTS exhausted) is never retried either.


def new_delivery_entry() -> dict:
    """Fresh per-recipient delivery record before any attempt."""
    return {"status": "pending", "attempts": 0, "last_attempt": None, "last_error": None}


def is_due_for_retry(delivery: dict, now: datetime) -> bool:
    """True if this pending delivery should be retried at `now`."""
    if delivery["status"] != "pending":
        return False
    attempts = delivery["attempts"]
    if attempts >= MAX_ATTEMPTS:
        return False  # should already be marked "failed"
    if attempts == 0 or not delivery.get("last_attempt"):
        return True  # never tried — retry immediately
    last = datetime.fromisoformat(delivery["last_attempt"])
    delay = BACKOFF_SCHEDULE[attempts - 1]
    return now >= last + timedelta(seconds=delay)


def _build_state_entry(j: dict, feed: dict, now_iso: str, silent: bool) -> dict:
    """Create fresh state entry for a newly-seen job.
    In silent/debug mode we pre-mark deliveries as 'sent' so we never spam
    historical listings — but with attempts=0 to flag they were not actually
    delivered (useful for analytics later)."""
    initial = (
        {"status": "sent", "attempts": 0, "last_attempt": now_iso, "last_error": None}
        if silent
        else new_delivery_entry()
    )
    return {
        "title": j["title"],
        "feed": feed["name"],
        "first_seen": now_iso,
        "delivery": {cid: dict(initial) for cid in feed["recipients"]},
    }


def migrate_state(state: dict, feeds: list[dict]) -> int:
    """Upgrade legacy per-job 'status' schema to per-recipient 'delivery' schema.
    Idempotent: entries already in new format pass through unchanged.
    Returns the count of migrated entries."""
    feed_by_name = {f["name"]: f for f in feeds}
    migrated = 0
    for link, entry in list(state.items()):
        if "delivery" in entry:
            continue
        old_status = entry.get("status", "sent")
        feed = feed_by_name.get(entry.get("feed", ""))
        recipients = feed["recipients"] if feed else []
        first_seen = entry.get("first_seen") or datetime.now().isoformat(timespec="seconds")
        delivery = {}
        for cid in recipients:
            if old_status == "sent":
                delivery[cid] = {
                    "status": "sent",
                    "attempts": 1,
                    "last_attempt": first_seen,
                    "last_error": None,
                }
            else:
                # "pending" or anything unknown — restart the retry cycle
                delivery[cid] = new_delivery_entry()
        state[link] = {
            "title": entry.get("title", ""),
            "feed": entry.get("feed", ""),
            "first_seen": first_seen,
            "delivery": delivery,
        }
        migrated += 1
    if migrated:
        log.info("Migrated %d state entries to per-recipient delivery schema", migrated)
    return migrated


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        # migrate old flat list format
        if isinstance(data, list):
            log.info("Migrating seen_jobs.json from list to dict format")
            return {link: {"title": "", "status": "sent", "feed": "", "first_seen": ""} for link in data}
        return data
    except Exception as e:
        log.error("seen_jobs.json is corrupted (%s) — starting with empty state", e)
        backup = STATE_FILE.with_suffix(".json.bak")
        STATE_FILE.rename(backup)
        log.info("Corrupted state saved to %s", backup)
        return {}


def save_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.error("Failed to save state: %s", e)


async def send_telegram(session: aiohttp.ClientSession, token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": DISABLE_WEB_PAGE_PREVIEW,
    }
    async with session.post(url, json=payload) as resp:
        if resp.status >= 400:
            body = (await resp.text())[:300]
            raise RuntimeError(f"{resp.status} {resp.reason}: {body}")


async def fetch_jobs(session: aiohttp.ClientSession, url: str) -> list[dict]:
    async with session.get(url) as resp:
        resp.raise_for_status()
        content = await resp.read()
    root = ET.fromstring(content)
    jobs = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        if link:
            jobs.append({"title": title, "link": link, "pubDate": pub_date})
    return jobs


def format_message(j: dict, feed_name: str) -> str:
    title = j["title"]
    m = SALARY_RE.search(title)
    salary_line = f"💰 <b>{m.group().replace(' ', '')}</b>\n" if m else ""
    return (
        f"🆕 <b>New vacancy</b>\n"
        f"{salary_line}"
        f"🔍 <b>Search:</b> {feed_name}\n"
        f"📌 <a href=\"{j['link']}\">{title}</a>"
    )


async def deliver_one(session: aiohttp.ClientSession, link: str, j: dict, feed_name: str,
                      chat_id: str, token: str, state: dict, now: datetime) -> bool:
    """Attempt one delivery to one recipient. Mutates state[link]['delivery'][chat_id]
    in place. Returns True iff the message was successfully delivered now (or was
    already 'sent' previously — idempotent)."""
    delivery = state[link]["delivery"].setdefault(chat_id, new_delivery_entry())

    # Idempotency: never re-send to an already-delivered recipient
    if delivery["status"] == "sent":
        return True
    # Dead letter: never retry a failed delivery
    if delivery["status"] == "failed":
        return False

    delivery["attempts"] += 1
    delivery["last_attempt"] = now.isoformat(timespec="seconds")
    msg = format_message(j, feed_name)

    try:
        await send_telegram(session, token, chat_id, msg)
        delivery["status"] = "sent"
        delivery["last_error"] = None
        log.info("[SEND] %s ← %s → OK", chat_id, j["title"][:80])
        return True
    except Exception as e:
        err = str(e)[:300]
        delivery["last_error"] = err
        if delivery["attempts"] >= MAX_ATTEMPTS:
            delivery["status"] = "failed"
            log.error("[FAILED] %s ← %s giving up after %d attempts: %s",
                      chat_id, link, delivery["attempts"], err)
        else:
            delivery["status"] = "pending"
            log.warning("[SEND] %s ← %s FAIL attempt %d/%d: %s",
                        chat_id, link, delivery["attempts"], MAX_ATTEMPTS, err)
        return False


async def retry_pending(session: aiohttp.ClientSession, state: dict, feeds: list[dict],
                        token: str) -> int:
    """Retry every pending (link, chat_id) delivery that is due per backoff schedule.
    Retries run concurrently. Returns the count of deliveries that succeeded."""
    feed_by_name = {f["name"]: f for f in feeds}
    now = datetime.now()

    # Collect due (link, chat_id) pairs first so we can iterate safely while
    # deliver_one mutates the delivery dict.
    due: list[tuple[str, str]] = []
    for link, entry in state.items():
        if "delivery" not in entry:
            continue
        for chat_id, delivery in entry["delivery"].items():
            if is_due_for_retry(delivery, now):
                due.append((link, chat_id))

    if not due:
        return 0

    log.info("Retrying %d pending delivery(s)...", len(due))
    tasks = []
    for link, chat_id in due:
        entry = state[link]
        feed_name = entry.get("feed", "")
        if feed_name not in feed_by_name:
            log.warning("Feed '%s' no longer configured — skipping retry for %s", feed_name, link)
            continue
        j = {"title": entry.get("title", ""), "link": link}
        attempts_next = entry["delivery"][chat_id]["attempts"] + 1
        log.info("[RETRY] %s ← %s (attempt %d/%d)", chat_id, j["title"][:80], attempts_next, MAX_ATTEMPTS)
        tasks.append(deliver_one(session, link, j, feed_name, chat_id, token, state, now))

    if not tasks:
        return 0
    results = await asyncio.gather(*tasks, return_exceptions=True)
    delivered = 0
    for r in results:
        if isinstance(r, Exception):
            log.error("retry task raised: %s", r)
        elif r is True:
            delivered += 1
    return delivered


async def check_feed(session: aiohttp.ClientSession, feed: dict, state: dict, silent: bool,
                     token: str, debug: bool = False) -> int:
    """Fetch one feed, register new jobs in state, attempt delivery to each recipient.
    Returns the count of jobs that had at least one successful delivery this cycle."""
    try:
        jobs = await fetch_jobs(session, feed["url"])
    except Exception as e:
        log.error("[%s] fetch failed: %s", feed["name"], e)
        return 0

    new_jobs = [j for j in jobs if j["link"] not in state]
    now = datetime.now()
    now_iso = now.isoformat(timespec="seconds")

    if debug:
        log.info("[%s] total: %d, new: %d, seen: %d", feed["name"], len(jobs), len(new_jobs), len(jobs) - len(new_jobs))
        for j in new_jobs:
            log.info("  → %s\n    %s", j["title"], j["link"])
            # In debug mode, pre-mark as sent so a subsequent normal run does not spam them.
            state[j["link"]] = _build_state_entry(j, feed, now_iso, silent=True)
        return 0

    # 1) Persist-before-deliver: record every new job in state first, even if silent.
    #    This way a crash between fetch and Telegram never loses a vacancy.
    for j in new_jobs:
        state[j["link"]] = _build_state_entry(j, feed, now_iso, silent=silent)

    if silent:
        return 0

    # 2) Attempt delivery to each recipient independently (IPN-style), in parallel.
    notified = 0
    for j in new_jobs:
        log.info("[%s] NEW: %s", feed["name"], j["title"])
        log.info("  %s", j["link"])
        results = await asyncio.gather(
            *[deliver_one(session, j["link"], j, feed["name"], cid, token, state, now)
              for cid in feed["recipients"]],
            return_exceptions=True,
        )
        if any(r is True for r in results):
            notified += 1
    return notified


async def check(silent: bool, token: str, feeds: list[dict], debug: bool = False) -> int:
    """One full check cycle: load state, migrate, retry pendings, fetch all feeds
    concurrently, deliver new jobs, save state. The aiohttp ClientTimeout enforces
    a hard wall-clock limit on every HTTP call, so the cycle cannot hang
    indefinitely."""
    state = load_state()
    migrate_state(state, feeds)  # idempotent — runs only on legacy entries

    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT, headers=HEADERS) as session:
        if not silent and not debug:
            retried = await retry_pending(session, state, feeds, token)
            if retried:
                log.info("%d pending delivery(s) succeeded.", retried)

        # Fetch all feeds concurrently. Each feed's failure is isolated.
        results = await asyncio.gather(
            *[check_feed(session, f, state, silent, token, debug) for f in feeds],
            return_exceptions=True,
        )

    total = 0
    for feed, result in zip(feeds, results):
        if isinstance(result, Exception):
            log.error("[%s] check_feed raised: %s", feed["name"], result)
        else:
            total += result

    save_state(state)
    return total


async def async_main(args, token: str, feeds: list[dict]) -> None:
    if args.debug:
        log.info("[DEBUG] Current feed contents (no notifications sent):")
        await check(silent=True, token=token, feeds=feeds, debug=True)
        return

    if args.once:
        found = await check(silent=False, token=token, feeds=feeds)
        log.info("%d new listing(s)", found) if found else log.info("No new listings")
        return

    log.info("Interval: %d min | Press Ctrl+C to stop", args.interval)

    truly_first = not STATE_FILE.exists()
    if truly_first:
        log.info("First launch: indexing current listings silently...")
        await asyncio.wait_for(check(silent=True, token=token, feeds=feeds), timeout=CHECK_TIMEOUT)
        log.info("Done. Watching for new listings...")
    else:
        log.info("Checking for listings missed while offline...")
        found = await asyncio.wait_for(check(silent=False, token=token, feeds=feeds), timeout=CHECK_TIMEOUT)
        log.info("%d listing(s) sent.", found) if found else log.info("None missed.")

    while True:
        try:
            await asyncio.sleep(args.interval * 60)
            found = await asyncio.wait_for(
                check(silent=False, token=token, feeds=feeds),
                timeout=CHECK_TIMEOUT,
            )
            if not found:
                log.info("Checked — no new listings")
        except asyncio.TimeoutError:
            log.warning(
                "Check cycle timed out after %ds (VPN/network change?) — skipping, will retry next interval",
                CHECK_TIMEOUT,
            )
        except asyncio.CancelledError:
            log.info("Cancelled — shutting down")
            raise
        except Exception as e:
            log.exception("Unexpected error in main loop: %s — sleeping 60s before retry", e)
            await asyncio.sleep(60)


def main():
    config = load_config()
    apply_config(config)
    setup_logging(
        level=config["logging"]["level"],
        max_bytes=config["logging"]["max_bytes"],
        backup_count=config["logging"]["backup_count"],
    )

    parser = argparse.ArgumentParser(description="Multi-feed vacancy monitor with per-feed Telegram routing")
    parser.add_argument("--interval", type=int, default=config["interval_minutes"],
                        help=f"Poll interval in minutes (default: {config['interval_minutes']} from config.json)")
    parser.add_argument("--once", action="store_true", help="Single check and exit")
    parser.add_argument("--debug", action="store_true", help="Show feed item counts and new listings without sending notifications")
    args = parser.parse_args()

    # --once and --debug don't need a lock
    if not args.once and not args.debug:
        acquire_lock()

    try:
        token = load_env()
        if not token:
            log.error("TELEGRAM_TOKEN missing in .env")
            return

        feeds = load_feeds()

        log.info("Starting vacancy monitor (PID %d)", os.getpid())
        for f in feeds:
            log.info("  Feed: %s → recipients: %s", f["name"], ", ".join(f["recipients"]))
        log.info("State: %s", STATE_FILE)
        log.info("Log:   %s", LOG_FILE)

        try:
            asyncio.run(async_main(args, token, feeds))
        except KeyboardInterrupt:
            log.info("Stopped by user")
    finally:
        if not args.once and not args.debug:
            release_lock()


if __name__ == "__main__":
    main()
