"""
core/settings.py — application config loaded from env vars.

Required vars: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Optional vars (have defaults): LLM_MODEL, PROFILE_MD_PATH, DB_PATH, KMP_BASE_URL,
                               CANDIDATE_NAME, CALLBACK_CV_PATH

Fails fast on startup if required vars are missing — never starts in broken state.

Usage:
    settings = load_settings()   # reads .env then env
    print(settings.llm_model)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Load .env file if present (don't fail if absent — prod uses real env vars)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional; env vars may be set by Docker / shell


@dataclass(frozen=True)
class Settings:
    # ── Required ──────────────────────────────────────────────────────────────
    anthropic_api_key: str
    telegram_token: str
    telegram_chat_id: int

    # ── Optional with defaults ─────────────────────────────────────────────────
    llm_model: str = "claude-opus-4-5"
    profile_md_path: Path = field(default_factory=lambda: Path("../callback-cv/skill/PROFILE.md"))
    db_path: Path = field(default_factory=lambda: Path("db/agent.db"))
    kmp_base_url: str = "http://localhost:8001"
    vacancies_path: Path = field(default_factory=lambda: Path("vacancies"))
    max_tokens: int = 4096
    candidate_name: str = "Candidate"
    callback_cv_path: Path = field(default_factory=lambda: Path("../callback-cv"))


class ConfigError(Exception):
    """Raised on startup when required env vars are missing."""


def load_settings() -> Settings:
    """Load Settings from environment. Raises ConfigError on missing required vars."""
    missing: list[str] = []

    def _require(name: str) -> str:
        val = os.getenv(name, "").strip()
        if not val:
            missing.append(name)
        return val

    def _optional(name: str, default: str) -> str:
        return os.getenv(name, default).strip() or default

    api_key        = _require("ANTHROPIC_API_KEY")
    telegram_token = _require("TELEGRAM_BOT_TOKEN")
    chat_id_str    = _require("TELEGRAM_CHAT_ID")

    if missing:
        raise ConfigError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example → .env and fill in the values."
        )

    try:
        chat_id = int(chat_id_str)
    except ValueError:
        raise ConfigError(f"TELEGRAM_CHAT_ID must be an integer, got: {chat_id_str!r}")

    return Settings(
        anthropic_api_key=api_key,
        telegram_token=telegram_token,
        telegram_chat_id=chat_id,
        llm_model=_optional("LLM_MODEL", "claude-opus-4-5"),
        profile_md_path=Path(_optional(
            "PROFILE_MD_PATH", "../callback-cv/skill/PROFILE.md"
        )),
        db_path=Path(_optional("DB_PATH", "db/agent.db")),
        kmp_base_url=_optional("KMP_BASE_URL", "http://localhost:8001"),
        vacancies_path=Path(_optional("VACANCIES_PATH", "vacancies")),
        max_tokens=int(_optional("MAX_TOKENS", "4096")),
        candidate_name=_optional("CANDIDATE_NAME", "Candidate"),
        callback_cv_path=Path(_optional("CALLBACK_CV_PATH", "../callback-cv")),
    )
