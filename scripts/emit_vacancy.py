#!/usr/bin/env python3
"""
scripts/emit_vacancy.py — Emit a test vacancy into seen_jobs.json.

Simulates what job-board-monitor does when it finds a new job posting.
The RSSWatcher (core/rss_watcher.py) will pick up the URL on its next poll.

Usage:
    # Add a vacancy (RSS watcher picks it up automatically)
    python scripts/emit_vacancy.py https://djinni.co/jobs/123/

    # Add with optional title (for readability in the file)
    python scripts/emit_vacancy.py https://djinni.co/jobs/123/ --title "Senior Backend Dev"

    # Use a custom seen_jobs.json path (e.g. from job-board-monitor repo)
    python scripts/emit_vacancy.py https://djinni.co/jobs/123/ --file ../job-board-monitor/seen_jobs.json

    # List current entries
    python scripts/emit_vacancy.py --list

    # Clear all entries (reset RSS state)
    python scripts/emit_vacancy.py --clear
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_DEFAULT_FILE = Path("seen_jobs.json")


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        print(f"⚠️  Error reading {path}: {exc}", file=sys.stderr)
        return []


def _save(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Emit a test vacancy into seen_jobs.json (RSS channel emulator)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", nargs="?", help="Job posting URL to add")
    parser.add_argument("--title", default="", help="Job title hint (optional)")
    parser.add_argument(
        "--file",
        default=str(_DEFAULT_FILE),
        metavar="PATH",
        help=f"Path to seen_jobs.json (default: {_DEFAULT_FILE})",
    )
    parser.add_argument("--list", action="store_true", help="List current entries and exit")
    parser.add_argument("--clear", action="store_true", help="Clear all entries and exit")
    args = parser.parse_args()

    path = Path(args.file)

    # ── --list ────────────────────────────────────────────────────────────────
    if args.list:
        entries = _load(path)
        if not entries:
            print(f"📭 {path} is empty or does not exist")
            return
        print(f"📋 {path} — {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}:")
        for i, e in enumerate(entries, 1):
            title = f" [{e['title']}]" if e.get("title") else ""
            print(f"  {i}. {e.get('url', '?')}{title} @ {e.get('seen_at', '?')}")
        return

    # ── --clear ───────────────────────────────────────────────────────────────
    if args.clear:
        _save(path, [])
        print(f"🗑️  Cleared {path}")
        return

    # ── Add URL ───────────────────────────────────────────────────────────────
    if not args.url:
        parser.print_help()
        sys.exit(1)

    url = args.url.strip()
    entries = _load(path)
    existing_urls = {e.get("url") for e in entries}

    if url in existing_urls:
        print(f"⚠️  Already in {path}:")
        print(f"   {url}")
        print("   Use --clear to reset or choose a different URL.")
        return

    entry: dict = {
        "url": url,
        "title": args.title,
        "seen_at": datetime.now().isoformat(timespec="seconds"),
    }
    entries.append(entry)
    _save(path, entries)

    print(f"✅ Added to {path}:")
    print(f"   URL:      {url}")
    if args.title:
        print(f"   Title:    {args.title}")
    print(f"   Seen at:  {entry['seen_at']}")
    print()
    print("   RSSWatcher will pick it up on the next poll cycle.")
    print(f"   (Default poll interval: 60s — override with RSS_POLL_INTERVAL env var)")


if __name__ == "__main__":
    main()
