"""
agent.py — agent-hub entry point.

Startup sequence:
1. Load Settings from env
2. Configure + initialise SQLite DB
3. Build ClaudeProvider (loads PROFILE.md for prompt caching)
4. Build ToolRegistry + register domain tools
5. Build Router (PydanticAI Agent)
6. Build TelegramBot
7. Start long polling (blocks until Ctrl-C or SIGTERM)

Run:
    python agent.py
"""

import asyncio
import logging
import signal
import sys

from adapters.cv_adapter import CVAdapter
from adapters.kmp_adapter import KMPAdapter
from core.deps import AgentDeps
from core.settings import ConfigError, load_settings
from core.llm_client import ClaudeProvider
from core.tool_registry import ToolRegistry
from core.router import Router
from core.telegram import TelegramBot
from db import database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agent")


def _register_tools(registry: ToolRegistry, llm: ClaudeProvider) -> None:
    """Register all domain tools.

    Tools are imported here to avoid circular imports.
    Each EPIC (7–11) adds its tools in this function.
    """
    from tools.cv_fetch_jd import cv_fetch_jd
    registry.register(cv_fetch_jd)

    from tools.cv_analyze import cv_analyze
    registry.register(cv_analyze)

    from tools.cv_generate import cv_generate
    registry.register(cv_generate)

    from tools.cv_cover import cv_cover
    registry.register(cv_cover)

    from tools.cv_get_tracker import cv_get_tracker
    registry.register(cv_get_tracker)

    log.info("ToolRegistry: %d tools registered — %s", len(registry), registry.names())


async def main() -> None:
    # ── 1. Config ─────────────────────────────────────────────────────────────
    try:
        settings = load_settings()
    except ConfigError as exc:
        log.error("Config error: %s", exc)
        sys.exit(1)

    log.info("Settings loaded — model=%s chat_id=%d", settings.llm_model, settings.telegram_chat_id)

    # ── 2. Database ───────────────────────────────────────────────────────────
    database.configure(settings.db_path)
    await database.init_db()

    # ── 3. LLM client ─────────────────────────────────────────────────────────
    if not settings.profile_md_path.exists():
        log.warning("PROFILE.md not found at %s — prompt caching disabled", settings.profile_md_path)
        profile_md = "# PROFILE\n(not loaded)"
    else:
        profile_md = settings.profile_md_path.read_text(encoding="utf-8")
        log.info("PROFILE.md loaded (%d chars)", len(profile_md))

    llm = ClaudeProvider(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        profile_md=profile_md,
        max_tokens=settings.max_tokens,
    )

    # ── 4. Tools + deps ──────────────────────────────────────────────────────
    settings.vacancies_path.mkdir(parents=True, exist_ok=True)

    kmp_adapter = KMPAdapter(base_url=settings.kmp_base_url)
    cv_adapter = CVAdapter(callback_cv_path=settings.callback_cv_path)
    deps = AgentDeps(
        kmp_adapter=kmp_adapter,
        llm=llm,
        vacancies_path=settings.vacancies_path,
        candidate_name=settings.candidate_name,
        cv_adapter=cv_adapter,
    )

    registry = ToolRegistry()
    _register_tools(registry, llm)

    # ── 5. Router ─────────────────────────────────────────────────────────────
    router = Router(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        registry=registry,
        deps=deps,
    )

    # ── 6. Telegram bot ───────────────────────────────────────────────────────
    bot = TelegramBot(
        token=settings.telegram_token,
        allowed_chat_id=settings.telegram_chat_id,
        on_message=router.handle,
    )

    # ── 7. Run ────────────────────────────────────────────────────────────────
    log.info("agent-hub starting — waiting for messages")

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        log.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass  # Windows — signals handled via KeyboardInterrupt

    try:
        await bot.start()
    except KeyboardInterrupt:
        pass
    finally:
        await bot.stop()
        log.info("agent-hub stopped")


if __name__ == "__main__":
    asyncio.run(main())
