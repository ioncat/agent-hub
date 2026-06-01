"""
core/onboarding.py — Onboarding FSM states and business logic.

Flow:
    /start → check DB for existing profile
           → profile exists: regular greeting
           → no profile: start wizard
               awaiting_name → awaiting_skill → awaiting_pdf → done

Interview is a stub — full design: docs/discovery/core-differentiators.md — AI Interview System.
"""

import json
import logging
from pathlib import Path

from aiogram.fsm.state import State, StatesGroup

from db import database

log = logging.getLogger(__name__)

VALID_SKILL_TYPES: tuple[str, ...] = ("pm", "generic")
SKILL_LABELS: dict[str, str] = {"pm": "Product Manager (PM)", "generic": "Generic / Other"}


class OnboardingStates(StatesGroup):
    awaiting_name  = State()
    awaiting_skill = State()
    awaiting_pdf   = State()
    interview      = State()


async def get_or_create_user_by_chat_id(telegram_chat_id: int) -> int:
    """Return user_id for telegram_chat_id, inserting a blank record on first visit."""
    row = await database.get_user_by_telegram_id(telegram_chat_id)
    if row is not None:
        return row["id"]
    return await database.insert_user(name="", telegram_chat_id=telegram_chat_id)


def parse_pdf(file_path: Path) -> str:
    """Extract plain text from a PDF using pypdf (sync).

    Raises RuntimeError if pypdf is not installed.
    Raises ValueError if the PDF produces no text (scanned image, protected).
    """
    try:
        import pypdf  # type: ignore[import]
    except ImportError:
        raise RuntimeError("pypdf not installed — run: pip install pypdf")

    reader = pypdf.PdfReader(str(file_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(p for p in pages if p.strip())
    if not text.strip():
        raise ValueError(
            "PDF produced no text — may be scanned image or password-protected. "
            "Try uploading a text-based PDF or paste the CV text directly."
        )
    return text


def synthesise_profile_stub(cv_text: str, name: str, skill_type: str) -> str:
    """Return a stub profile JSON from CV text, without running the LLM interview.

    STUB — replace with full AI interview system.
    See: docs/discovery/core-differentiators.md — AI Interview System.

    ClaudeProvider reads this JSON as the system-prompt profile.
    When interview_completed=False the pipeline still runs but with reduced profile depth.
    """
    profile: dict = {
        "name": name,
        "skill_type": skill_type,
        "cv_raw": cv_text[:10_000],
        "onboarding_source": "pdf_upload_stub",
        "interview_completed": False,
        "_stub_note": (
            "AI interview not yet conducted. "
            "Profile built from raw CV text only. "
            "Run /update_profile to start the interview."
        ),
    }
    return json.dumps(profile, ensure_ascii=False, indent=2)
