"""
tools/cv_onboard.py — Onboarding profile synthesis tool.

Orchestrates the profile build from CV text:
  Phase 1: (stub) synthesise profile JSON from CV text → store in DB
  Phase 2: (future) LLM interview — generate questions, multi-turn, synthesise transcript

Called directly (not via ToolRegistry) from core/telegram.py onboarding FSM handlers.

Phase 2 (LLM interview) is a competitive differentiator — full design required.
See: docs/discovery/core-differentiators.md — AI Interview System.
"""

import logging
from pathlib import Path

from core.onboarding import synthesise_profile_stub
from db import database

log = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


async def build_profile_from_cv(
    user_id: int,
    name: str,
    skill_type: str,
    cv_text: str,
) -> str:
    """Build and persist a user profile from parsed CV text.

    Current implementation: stub synthesis (no LLM interview).
    Future: load prompts/[skill_type]/onboarding_interview.md, run multi-turn interview,
    synthesise transcript into structured profile JSON.

    Returns:
        Profile JSON string (also saved to DB).
    """
    log.info(
        "cv_onboard: building profile for user_id=%d skill_type=%s cv_len=%d",
        user_id, skill_type, len(cv_text),
    )

    # ── Load interview prompt (for future use) ────────────────────────────────
    interview_prompt_path = _PROMPTS_DIR / skill_type / "onboarding_interview.md"
    if not interview_prompt_path.exists():
        interview_prompt_path = _PROMPTS_DIR / "generic" / "onboarding_interview.md"
    # NOTE: prompt loaded but not used until LLM interview is designed.
    # See docs/discovery/core-differentiators.md — AI Interview System.

    # ── Stub: synthesise profile from CV without interview ────────────────────
    profile_json = synthesise_profile_stub(cv_text=cv_text, name=name, skill_type=skill_type)

    # ── Persist ───────────────────────────────────────────────────────────────
    await database.upsert_user(user_id=user_id, name=name, skill_type=skill_type)
    await database.update_user_profile(user_id, profile_json)
    await database.update_user_onboarding_step(user_id, None)

    log.info("cv_onboard: profile saved for user_id=%d", user_id)
    return profile_json


async def get_profile_for_llm(user_id: int) -> str:
    """Return the profile text to inject as LLM system prompt context.

    If no profile exists, returns a minimal fallback so the pipeline still runs.
    Called by ClaudeProvider when loading profile from DB (EPIC-17 Chunk 4).
    """
    profile_json = await database.get_user_profile(user_id)
    if profile_json:
        return f"# Candidate Profile\n\n```json\n{profile_json}\n```"

    log.warning("cv_onboard: no profile for user_id=%d — using fallback", user_id)
    return (
        "# Candidate Profile\n\n"
        "_Profile not yet created. User has not completed onboarding._\n\n"
        "Analyse vacancies with limited personalisation until /start onboarding is completed."
    )
