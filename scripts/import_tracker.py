#!/usr/bin/env python3
"""
scripts/import_tracker.py — Import historical vacancies from callback-cv/tracker.json into SQLite.

Reads tracker.json, maps each entry to its vacancy folder in callback-cv/vacancies/processing/,
resolves markdown_path so reader.py can find JD_analysis.md, inserts rows into vacancies table.

Idempotent: duplicates by URL are skipped.

Status derived from tracker.json flags:
    cover=true  → cover_generated
    cv=true     → cv_generated
    analysis=true → analyzed
    else        → fetched

Usage:
    python scripts/import_tracker.py
    python scripts/import_tracker.py --dry-run
    python scripts/import_tracker.py --tracker ../callback-cv/tracker.json
    python scripts/import_tracker.py --callback-cv /path/to/callback-cv --db db/agent.db
"""

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

# Windows cp1252 → force UTF-8 so emoji in print() don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import database


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_site(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if "djinni" in netloc:
        return "djinni"
    if "dou.ua" in netloc:
        return "dou"
    if "linkedin" in netloc:
        return "linkedin"
    return "other"


def _derive_status(entry: dict) -> str:
    if entry.get("cover"):
        return "cover_generated"
    if entry.get("cv"):
        return "cv_generated"
    if entry.get("analysis"):
        return "analyzed"
    return "fetched"


def _find_vacancy_folder(processing_root: Path, vacancy_name: str) -> Path | None:
    """Match tracker.json vacancy name to a folder in vacancies/processing/."""
    candidate = processing_root / vacancy_name
    return candidate if candidate.is_dir() else None


def _find_primary_md(folder: Path, vacancy_name: str) -> Path | None:
    """Find the primary JD-like .md file in vacancy folder.

    Priority: JD.md → {vacancy_name}.md → any .md except JD_analysis.md.
    Falls back to JD_analysis.md itself (parent dir still resolves for reader.py).
    """
    for candidate in [folder / "JD.md", folder / f"{vacancy_name}.md"]:
        if candidate.exists():
            return candidate

    for md in sorted(folder.glob("*.md")):
        if md.name != "JD_analysis.md":
            return md

    fallback = folder / "JD_analysis.md"
    return fallback if fallback.exists() else None


# ── Import logic ──────────────────────────────────────────────────────────────

async def import_tracker(
    tracker_path: Path,
    callback_cv_path: Path,
    dry_run: bool = False,
) -> None:
    processing_root = callback_cv_path / "vacancies" / "processing"

    if not tracker_path.exists():
        print(f"❌  tracker.json not found: {tracker_path}")
        sys.exit(1)

    entries: list[dict] = json.loads(tracker_path.read_text(encoding="utf-8"))
    print(f"📋  {len(entries)} entries in tracker.json")

    skipped = 0
    imported = 0
    no_folder = 0

    for entry in entries:
        vacancy_name: str = entry.get("vacancy", "").strip()
        url: str          = entry.get("source", "").strip()
        date: str         = entry.get("date", "")

        if not url:
            print(f"  ⚠️   skip (no URL): {vacancy_name!r}")
            skipped += 1
            continue

        # ── Resolve filesystem path ───────────────────────────────────────────
        folder = _find_vacancy_folder(processing_root, vacancy_name)
        markdown_path: str | None = None

        if folder:
            primary_md = _find_primary_md(folder, vacancy_name)
            if primary_md:
                markdown_path = str(primary_md)
        else:
            no_folder += 1

        site   = _detect_site(url)
        status = _derive_status(entry)

        if dry_run:
            folder_tag = str(folder.relative_to(callback_cv_path)) if folder else "⚠️  no folder"
            print(f"  [DRY] {status:18s} | {entry.get('fit_rate', '—'):6s} | {vacancy_name[:55]}")
            print(f"         {folder_tag}")
            continue

        # ── Insert (skip duplicates) ──────────────────────────────────────────
        try:
            vacancy_id = await database.insert_vacancy(
                url=url,
                title=vacancy_name,
                site=site,
                markdown_path=markdown_path,
            )
            # Set correct status (insert_vacancy defaults to 'fetched')
            if status != "fetched":
                await database.update_vacancy_status(vacancy_id, status)

            imported += 1
            print(f"  ✅  #{vacancy_id:3d} {status:18s} | {vacancy_name[:55]}")

        except Exception as exc:
            if "UNIQUE constraint" in str(exc) or "IntegrityError" in str(exc):
                skipped += 1
                print(f"  —   skip (duplicate): {vacancy_name[:55]}")
            else:
                print(f"  ❌  error ({vacancy_name[:40]}): {exc}")
                skipped += 1

    print()
    if dry_run:
        print(f"DRY RUN — nothing written. {len(entries)} entries, {no_folder} without folder.")
    else:
        print(f"Done. Imported: {imported} | Skipped: {skipped} | No folder: {no_folder}")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import historical vacancies from tracker.json into SQLite"
    )
    parser.add_argument(
        "--tracker",
        default=None,
        metavar="PATH",
        help="Path to tracker.json (default: CALLBACK_CV_PATH/tracker.json)",
    )
    parser.add_argument(
        "--callback-cv",
        default="../callback-cv",
        metavar="PATH",
        help="Path to callback-cv repo (default: ../callback-cv)",
    )
    parser.add_argument(
        "--db",
        default="db/agent.db",
        metavar="PATH",
        help="Path to SQLite DB (default: db/agent.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without writing to DB",
    )
    args = parser.parse_args()

    callback_cv_path = Path(args.callback_cv).resolve()
    tracker_path = Path(args.tracker).resolve() if args.tracker else (callback_cv_path / "tracker.json")
    db_path = Path(args.db).resolve()

    print(f"tracker.json : {tracker_path}")
    print(f"callback-cv  : {callback_cv_path}")
    print(f"DB           : {db_path}")
    print(f"Dry run      : {args.dry_run}")
    print()

    if not args.dry_run:
        database.configure(db_path)
        await database.init_db()

    await import_tracker(tracker_path, callback_cv_path, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
