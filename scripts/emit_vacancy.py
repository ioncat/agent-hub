#!/usr/bin/env python3
"""
scripts/emit_vacancy.py — Queue a test vacancy into career-agent via webhook.

Simulates what job-monitor does: POSTs to POST /api/new-vacancy.
RSSWatcher picks it up on next DB poll and runs cv_fetch_jd.

Requires:
    web-tracker running on WEB_TRACKER_URL (default http://localhost:8080)

Usage:
    # Queue a vacancy (RSSWatcher picks it up automatically)
    python scripts/emit_vacancy.py https://djinni.co/jobs/123/

    # With optional title and user_id
    python scripts/emit_vacancy.py https://djinni.co/jobs/123/ --title "Senior PM" --user-id 1

    # List queued vacancies (status=queued in DB)
    python scripts/emit_vacancy.py --list

    # Custom tracker URL
    python scripts/emit_vacancy.py https://... --tracker http://localhost:8080
"""

import argparse
import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=True)
except ImportError:
    pass


async def emit(url: str, title: str, user_id: int, tracker_url: str) -> None:
    try:
        import httpx
    except ImportError:
        print("❌  httpx not installed: pip install httpx")
        sys.exit(1)

    endpoint = f"{tracker_url.rstrip('/')}/api/new-vacancy"
    payload = {"url": url, "user_id": user_id}
    if title:
        payload["title"] = title

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(endpoint, json=payload)
        except httpx.ConnectError:
            print(f"❌  Cannot connect to {endpoint}")
            print("    Start web-tracker: uvicorn web.api:app --reload")
            sys.exit(1)

    if resp.status_code == 201:
        data = resp.json()
        print(f"✅  Queued:")
        print(f"   URL:        {url}")
        print(f"   vacancy_id: #{data['vacancy_id']}")
        print(f"   status:     {data['status']}")
        print()
        print("   RSSWatcher will pick it up on next poll cycle (default: 30s).")
    elif resp.status_code == 409:
        print(f"⚠️  Already in DB: {url}")
    else:
        print(f"❌  Unexpected response: {resp.status_code}")
        print(f"    {resp.text[:300]}")
        sys.exit(1)


async def list_queued(tracker_url: str) -> None:
    try:
        import httpx
    except ImportError:
        print("❌  httpx not installed: pip install httpx")
        sys.exit(1)

    endpoint = f"{tracker_url.rstrip('/')}/api/vacancies?status=queued&limit=50"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(endpoint)
        except httpx.ConnectError:
            print(f"❌  Cannot connect to {endpoint}")
            sys.exit(1)

    rows = resp.json()
    if not rows:
        print("📭  No queued vacancies.")
        return
    print(f"📋  Queued vacancies ({len(rows)}):")
    for r in rows:
        print(f"  #{r['id']}  {r['url'][:80]}  [{r.get('title') or '—'}]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Queue a test vacancy into career-agent via POST /api/new-vacancy"
    )
    parser.add_argument("url", nargs="?", help="Job posting URL to queue")
    parser.add_argument("--title", default="", help="Job title hint (optional)")
    parser.add_argument("--user-id", type=int, default=1, dest="user_id",
                        help="career-agent user_id (default: 1)")
    parser.add_argument("--tracker", default="http://localhost:8080", dest="tracker_url",
                        metavar="URL", help="Web-tracker base URL (default: http://localhost:8080)")
    parser.add_argument("--list", action="store_true", help="List queued vacancies and exit")
    args = parser.parse_args()

    if args.list:
        asyncio.run(list_queued(args.tracker_url))
        return

    if not args.url:
        parser.print_help()
        sys.exit(1)

    asyncio.run(emit(args.url, args.title, args.user_id, args.tracker_url))


if __name__ == "__main__":
    main()
