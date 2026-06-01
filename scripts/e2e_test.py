#!/usr/bin/env python3
"""
scripts/e2e_test.py — Manual end-to-end pipeline test.

Runs cv_fetch_jd → cv_analyze on a real vacancy URL.
Does NOT send Telegram messages — prints output to stdout.

Requires:
    - .env with ANTHROPIC_API_KEY (and AGENT_MODE=testing for confirmation)
    - kmp-service running on KMP_BASE_URL (default http://localhost:8001)
    - DB at DB_PATH (default db/agent.db)

Usage:
    python scripts/e2e_test.py
    python scripts/e2e_test.py --url https://jobs.dou.ua/companies/.../
    python scripts/e2e_test.py --phase fetch          # only fetch JD
    python scripts/e2e_test.py --phase fetch,analyze  # fetch + analyze
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


async def run_e2e(url: str, phases: list[str]) -> None:
    print(f"\n{'='*60}")
    print(f"  career-agent e2e test")
    print(f"  URL: {url}")
    print(f"  Phases: {', '.join(phases)}")
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
    cv_adapter = CVAdapter(callback_cv_path=settings.callback_cv_path)

    deps = AgentDeps(
        kmp_adapter=kmp,
        llm=llm,
        vacancies_path=settings.vacancies_path,
        candidate_name=settings.candidate_name,
        cv_adapter=cv_adapter,
    )
    ctx = _Ctx(deps=deps)

    # ── Health check ──────────────────────────────────────────────────────────
    print("🔍  Checking kmp-service health…")
    if not await kmp.health():
        print(f"❌  kmp-service unreachable at {settings.kmp_base_url}")
        print("    Start it: cd knowledge-mirror-parser && python -m uvicorn api:app --port 8001")
        sys.exit(1)
    print("✅  kmp-service healthy\n")

    # ── Phase: fetch ──────────────────────────────────────────────────────────
    vacancy_id: int | None = None

    if "fetch" in phases:
        print("📄  Phase: cv_fetch_jd")
        from tools.cv_fetch_jd import cv_fetch_jd
        result = await cv_fetch_jd(ctx, url)  # type: ignore[arg-type]
        print(f"\n--- cv_fetch_jd result ---\n{result}\n")

        # Get vacancy_id from DB
        from db.database import get_vacancy_by_url
        row = await get_vacancy_by_url(url)
        if row:
            vacancy_id = row["id"]
            print(f"  DB vacancy_id: #{vacancy_id}\n")

    # ── Phase: analyze ────────────────────────────────────────────────────────
    if "analyze" in phases:
        if vacancy_id is None:
            from db.database import get_vacancy_by_url
            row = await get_vacancy_by_url(url)
            if not row:
                print("❌  Vacancy not in DB — run 'fetch' phase first")
                sys.exit(1)
            vacancy_id = row["id"]

        print(f"🔬  Phase: cv_analyze (vacancy #{vacancy_id})")
        from tools.cv_analyze import cv_analyze
        result = await cv_analyze(ctx, vacancy_id)  # type: ignore[arg-type]
        print(f"\n--- cv_analyze result ---\n{result}\n")

    # ── Phase: generate ───────────────────────────────────────────────────────
    if "generate" in phases:
        if vacancy_id is None:
            from db.database import get_vacancy_by_url
            row = await get_vacancy_by_url(url)
            if not row:
                print("❌  Vacancy not in DB — run 'fetch' phase first")
                sys.exit(1)
            vacancy_id = row["id"]

        print(f"📝  Phase: cv_generate (vacancy #{vacancy_id})")
        from tools.cv_generate import cv_generate
        result = await cv_generate(ctx, vacancy_id)  # type: ignore[arg-type]
        print(f"\n--- cv_generate result ---\n{result}\n")

    # ── Phase: cover ──────────────────────────────────────────────────────────
    if "cover" in phases:
        if vacancy_id is None:
            from db.database import get_vacancy_by_url
            row = await get_vacancy_by_url(url)
            if not row:
                print("❌  Vacancy not in DB — run 'fetch' phase first")
                sys.exit(1)
            vacancy_id = row["id"]

        print(f"✉️   Phase: cv_cover (vacancy #{vacancy_id})")
        from tools.cv_cover import cv_cover
        result = await cv_cover(ctx, vacancy_id)  # type: ignore[arg-type]
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
    parser = argparse.ArgumentParser(description="End-to-end pipeline test")
    parser.add_argument("--url", default=_DEFAULT_URL, help="Vacancy URL to process")
    parser.add_argument(
        "--phase",
        default="fetch,analyze",
        help="Comma-separated phases: fetch,analyze,generate,cover (default: fetch,analyze)",
    )
    args = parser.parse_args()
    phases = [p.strip() for p in args.phase.split(",")]
    asyncio.run(run_e2e(args.url, phases))


if __name__ == "__main__":
    main()
