#!/usr/bin/env python3
"""
scripts/health_check.py — Lightweight service health monitor.

PURPOSE
-------
Fast no-cost check that all career-agent services are alive.
Does NOT call Claude API — DB and HTTP only.

CHECKS
------
    :PARSER_URL/health   — jd-parser (fetches JDs from web)
    :8002/health         — pdf-service (renders PDFs)
    db/agent.db          — SQLite reachable (SELECT 1)
    Telegram ping        — optional, only if --telegram flag

OUTPUT
------
    Console: one line per check, ✅/❌ prefix
    Exit 0  — all checks passed
    Exit 1  — one or more checks failed

TELEGRAM ALERT
--------------
    Sent if --telegram and any check failed.
    Uses TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID from .env.

USAGE
-----
    python scripts/health_check.py
    python scripts/health_check.py --telegram
    python scripts/health_check.py --pdf-url http://localhost:9002

SCHEDULE (Windows Task Scheduler)
----------------------------------
    Program:  python
    Args:     scripts/health_check.py --telegram
    Start in: E:\\path\\to\\career-agent
"""

import argparse
import asyncio
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass


# ── Config ────────────────────────────────────────────────────────────────────

PARSER_URL  = os.getenv("PARSER_URL", "http://localhost:8001")
PDF_URL     = os.getenv("PDF_SERVICE_URL", "http://localhost:8002")
DB_PATH     = Path(os.getenv("DB_PATH", str(_ROOT / "db" / "agent.db")))
BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID", "")

HTTP_TIMEOUT = 5  # seconds per request


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


# ── Checks ────────────────────────────────────────────────────────────────────

async def check_http(name: str, url: str) -> CheckResult:
    """GET {url}/health → expect 200 + {"status":"ok"}."""
    import urllib.request
    import urllib.error
    import json

    health_url = url.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(health_url, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            if data.get("status") == "ok":
                return CheckResult(name, ok=True, detail=health_url)
            return CheckResult(name, ok=False, detail=f"unexpected body: {body[:80]}")
    except urllib.error.URLError as exc:
        return CheckResult(name, ok=False, detail=str(exc.reason))
    except Exception as exc:
        return CheckResult(name, ok=False, detail=str(exc)[:120])


def check_db() -> CheckResult:
    """SQLite reachable: SELECT 1 from agent.db."""
    if not DB_PATH.exists():
        return CheckResult("sqlite", ok=False, detail=f"file not found: {DB_PATH}")
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=3)
        conn.execute("SELECT 1").fetchone()
        conn.close()
        # Also count vacancies as a sanity check
        conn = sqlite3.connect(str(DB_PATH), timeout=3)
        count = conn.execute("SELECT COUNT(*) FROM vacancies").fetchone()[0]
        conn.close()
        return CheckResult("sqlite", ok=True, detail=f"{DB_PATH.name} ({count} vacancies)")
    except Exception as exc:
        return CheckResult("sqlite", ok=False, detail=str(exc)[:120])


async def check_telegram_bot() -> CheckResult:
    """Telegram getMe — confirms bot token is valid."""
    if not BOT_TOKEN:
        return CheckResult("telegram", ok=False, detail="TELEGRAM_BOT_TOKEN not set")
    import urllib.request
    import json

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
                bot_name = data["result"].get("username", "?")
                return CheckResult("telegram", ok=True, detail=f"@{bot_name}")
            return CheckResult("telegram", ok=False, detail=str(data))
    except Exception as exc:
        return CheckResult("telegram", ok=False, detail=str(exc)[:120])


# ── Alert ─────────────────────────────────────────────────────────────────────

async def send_telegram_alert(failures: list[CheckResult]) -> None:
    """Send Telegram message listing failed checks."""
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️  Telegram alert skipped: BOT_TOKEN or CHAT_ID not set")
        return

    import urllib.request
    import urllib.parse
    import json

    lines = ["🔴 career-agent health check FAILED\n"]
    for f in failures:
        lines.append(f"❌ {f.name}: {f.detail}")

    text = "\n".join(lines)
    payload = json.dumps({"chat_id": CHAT_ID, "text": text}).encode("utf-8")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}),
            timeout=HTTP_TIMEOUT,
        ) as resp:
            resp.read()
        print("📨  Telegram alert sent")
    except Exception as exc:
        print(f"⚠️  Telegram alert failed: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> int:
    pdf_url = args.pdf_url or PDF_URL
    parser_url = args.parser_url or PARSER_URL

    results: list[CheckResult] = []

    # HTTP checks (run in parallel)
    http_tasks = [
        check_http("parser", parser_url),
        check_http("pdf-service", pdf_url),
    ]
    if args.telegram:
        http_tasks.append(check_telegram_bot())

    http_results = await asyncio.gather(*http_tasks)
    results.extend(http_results)

    # DB check (sync — fast)
    results.append(check_db())

    # Print results
    all_ok = True
    for r in results:
        icon = "✅" if r.ok else "❌"
        detail = f"  ({r.detail})" if r.detail else ""
        print(f"{icon}  {r.name}{detail}")
        if not r.ok:
            all_ok = False

    # Alert
    if not all_ok and args.telegram:
        failures = [r for r in results if not r.ok]
        await send_telegram_alert(failures)

    return 0 if all_ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lightweight health check for career-agent services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--telegram", action="store_true",
        help="Also check Telegram bot token + send alert on failure",
    )
    parser.add_argument(
        "--pdf-url", default=None,
        help=f"PDF service URL (default: {PDF_URL})",
    )
    parser.add_argument(
        "--parser-url", default=None,
        help=f"Parser service URL (default: {PARSER_URL})",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
