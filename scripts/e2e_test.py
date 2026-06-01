#!/usr/bin/env python3
"""
scripts/e2e_test.py — Manual end-to-end pipeline test.

Three input modes:
  --url URL         fetch JD from web, then run pipeline phases
  --file PATH.md    read JD from local .md file (skips fetch)
  --id VACANCY_ID   reprocess existing DB vacancy (skips fetch)

Does NOT send Telegram messages — prints output to stdout.

Requires:
    - .env with ANTHROPIC_API_KEY (and AGENT_MODE=testing for confirmation)
    - kmp-service on KMP_BASE_URL for --url mode (default http://localhost:8001)
    - DB at DB_PATH (default db/agent.db)

Usage:
    python scripts/e2e_test.py
    python scripts/e2e_test.py --url https://jobs.dou.ua/companies/.../
    python scripts/e2e_test.py --file vacancies/djinni/2026-06/123/JD.md
    python scripts/e2e_test.py --id 42
    python scripts/e2e_test.py --url https://... --phase fetch,analyze
    python scripts/e2e_test.py --id 42 --phase generate,cover
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

# Windows cp1252 → force UTF-8 output so emoji don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root on sys.path
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=True)
except ImportError:
    pass

from core.settings import load_settings, ConfigError
from core.llm_client import ClaudeProvider
from adapters.kmp_adapter import KMPAdapter
from adapters.cv_adapter import CVAdapter
from core.deps import AgentDeps
from db import database


_DEFAULT_URL = "https://jobs.dou.ua/companies/solar-digital/vacancies/360005/"


@dataclass
class _Ctx:
    """Minimal stand-in for PydanticAI RunContext."""
    deps: AgentDeps


async def run_e2e(
    url: str | None,
    phases: list[str],
    file_path: Path | None = None,
    vacancy_id: int | None = None,
) -> None:
    # Determine mode label for display
    if file_path:
        mode = f"file: {file_path}"
    elif vacancy_id is not None:
        mode = f"vacancy_id: #{vacancy_id}"
    else:
        mode = f"url: {url}"

    print(f"\n{'='*60}")
    print(f"  career-agent e2e test")
    print(f"  Input  : {mode}")
    print(f"  Phases : {', '.join(phases)}")
    print(f"{'='*60}\n")

    # ── Settings & services ───────────────────────────────────────────────────
    try:
        settings = load_settings()
    except ConfigError as e:
        print(f"❌  Config error: {e}")
        sys.exit(1)

    print(f"  AGENT_MODE  : {settings.agent_mode}")
    print(f"  KMP_BASE_URL: {settings.kmp_base_url}")
    print(f"  DB_PATH     : {settings.db_path}")
    print(f"  CANDIDATE   : {settings.candidate_name}")
    print()

    database.configure(settings.db_path)
    await database.init_db()

    profile_md = settings.profile_md_path.read_text(encoding="utf-8")
    print(f"  PROFILE.md  : {len(profile_md)} chars\n")

    llm = ClaudeProvider(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        profile_md=profile_md,
        max_tokens=settings.max_tokens,
        testing_mode=(settings.agent_mode == "testing"),
    )

    kmp = KMPAdapter(base_url=settings.kmp_base_url)
    cv_adapter = CVAdapter(pdf_service_url=settings.pdf_service_url)

    deps = AgentDeps(
        kmp_adapter=kmp,
        llm=llm,
        vacancies_path=settings.vacancies_path,
        candidate_name=settings.candidate_name,
        cv_adapter=cv_adapter,
        user_id=1,
        skill_type=settings.default_skill_type,
    )
    ctx = _Ctx(deps=deps)

    # ── Resolve vacancy_id from --id mode ─────────────────────────────────────
    resolved_vacancy_id: int | None = vacancy_id

    # ── Health check (only needed for URL fetch) ──────────────────────────────
    if "fetch" in phases and url and not file_path:
        print("🔍  Checking kmp-service health…")
        if not await kmp.health():
            print(f"❌  kmp-service unreachable at {settings.kmp_base_url}")
            print("    Start it: docker compose up kmp-service -d")
            sys.exit(1)
        print("✅  kmp-service healthy\n")

    # ── Phase: fetch (URL mode) ───────────────────────────────────────────────
    if "fetch" in phases and url and not file_path and resolved_vacancy_id is None:
        print("📄  Phase: cv_fetch_jd")
        from tools.cv_fetch_jd import cv_fetch_jd
        result = await cv_fetch_jd(ctx, url)  # type: ignore[arg-type]
        print(f"\n--- cv_fetch_jd result ---\n{result}\n")

        from db.database import get_vacancy_by_url
        row = await get_vacancy_by_url(url)
        if row:
            resolved_vacancy_id = row["id"]
            print(f"  DB vacancy_id: #{resolved_vacancy_id}\n")

    # ── Phase: fetch (file mode) ──────────────────────────────────────────────
    elif "fetch" in phases and file_path:
        print(f"📄  Phase: load JD from file — {file_path}")
        if not file_path.exists():
            print(f"❌  File not found: {file_path}")
            sys.exit(1)
        content = file_path.read_text(encoding="utf-8")
        # Extract title from first # heading
        title = "Vacancy"
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        synthetic_url = f"file://{file_path.resolve()}"
        from db.database import insert_vacancy, get_vacancy_by_url
        existing = await get_vacancy_by_url(synthetic_url)
        if existing:
            resolved_vacancy_id = existing["id"]
            print(f"  Already in DB: vacancy_id=#{resolved_vacancy_id}\n")
        else:
            resolved_vacancy_id = await insert_vacancy(
                url=synthetic_url,
                title=title,
                markdown_path=str(file_path.resolve()),
                user_id=1,
            )
            print(f"  Inserted into DB: vacancy_id=#{resolved_vacancy_id}\n")

    # ── --id mode: vacancy already in DB ─────────────────────────────────────
    elif resolved_vacancy_id is not None:
        from db.database import get_vacancy_by_id
        row = await get_vacancy_by_id(resolved_vacancy_id)
        if not row:
            print(f"❌  Vacancy #{resolved_vacancy_id} not found in DB")
            sys.exit(1)
        print(f"📂  Using existing vacancy #{resolved_vacancy_id}: {row['title'] or row['url']}\n")

    def _require_vacancy_id(phase_name: str) -> int:
        if resolved_vacancy_id is None:
            print(f"❌  No vacancy_id — run 'fetch' phase first or use --id")
            sys.exit(1)
        return resolved_vacancy_id

    # ── Phase: analyze ────────────────────────────────────────────────────────
    if "analyze" in phases:
        vid = _require_vacancy_id("analyze")
        print(f"🔬  Phase: cv_analyze (vacancy #{vid})")
        from tools.cv_analyze import cv_analyze
        result = await cv_analyze(ctx, vid)  # type: ignore[arg-type]
        print(f"\n--- cv_analyze result ---\n{result}\n")

    # ── Phase: generate ───────────────────────────────────────────────────────
    if "generate" in phases:
        vid = _require_vacancy_id("generate")
        print(f"📝  Phase: cv_generate (vacancy #{vid})")
        from tools.cv_generate import cv_generate
        result = await cv_generate(ctx, vid)  # type: ignore[arg-type]
        print(f"\n--- cv_generate result ---\n{result}\n")

    # ── Phase: cover ──────────────────────────────────────────────────────────
    if "cover" in phases:
        vid = _require_vacancy_id("cover")
        print(f"✉️   Phase: cv_cover (vacancy #{vid})")
        from tools.cv_cover import cv_cover
        result = await cv_cover(ctx, vid)  # type: ignore[arg-type]
        print(f"\n--- cv_cover result ---\n{result}\n")

    # ── Session cost summary ──────────────────────────────────────────────────
    s = llm.session_summary
    if s["calls"] > 0:
        print(f"\n💰  Session cost: {s['calls']} calls | "
              f"in={s['input_tokens']} out={s['output_tokens']} "
              f"cache_write={s['cache_write_tokens']} cache_read={s['cache_read_tokens']} "
              f"| total=${s['cost_usd']:.4f}")

    print("\n✅  e2e test complete")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end pipeline test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Input modes (mutually exclusive):
  --url URL       fetch from web (default if nothing specified)
  --file PATH.md  read JD from local file, skip fetch
  --id N          reprocess existing DB vacancy by ID, skip fetch

Examples:
  python scripts/e2e_test.py
  python scripts/e2e_test.py --url https://djinni.co/jobs/123/
  python scripts/e2e_test.py --file vacancies/djinni/2026-06/123/JD.md
  python scripts/e2e_test.py --id 42
  python scripts/e2e_test.py --id 42 --phase generate,cover
        """,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--url", default=None, help="Vacancy URL to process")
    group.add_argument("--file", dest="file_path", default=None, metavar="PATH",
                       help="Path to JD .md file (skips fetch phase)")
    group.add_argument("--id", dest="vacancy_id", type=int, default=None, metavar="N",
                       help="Existing DB vacancy ID (skips fetch phase)")
    parser.add_argument(
        "--phase",
        default=None,
        help="Comma-separated phases: fetch,analyze,generate,cover "
             "(default: fetch,analyze for URL; analyze,generate,cover for file/id)",
    )
    args = parser.parse_args()

    # Defaults
    file_path = Path(args.file_path) if args.file_path else None
    url = args.url or (_DEFAULT_URL if not file_path and args.vacancy_id is None else None)

    if args.phase:
        phases = [p.strip() for p in args.phase.split(",")]
    elif file_path or args.vacancy_id is not None:
        phases = ["analyze", "generate", "cover"]
    else:
        phases = ["fetch", "analyze"]

    asyncio.run(run_e2e(
        url=url,
        phases=phases,
        file_path=file_path,
        vacancy_id=args.vacancy_id,
    ))


if __name__ == "__main__":
    main()
