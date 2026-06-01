"""
tests/test_onboarding.py — tests for core/onboarding.py and tools/cv_onboard.py.

Covers:
  - OnboardingStates FSM states defined
  - parse_pdf: text extraction, empty-PDF error, missing-pypdf error
  - synthesise_profile_stub: valid JSON, required fields
  - get_or_create_user_by_chat_id: creates on first call, returns same id on second
  - build_profile_from_cv: persists profile to DB, returns JSON
  - get_profile_for_llm: returns formatted profile or fallback text
  - DB helpers: update_user_profile, get_user_profile, update_user_onboarding_step
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from db import database


@pytest_asyncio.fixture(autouse=True)
async def temp_db(tmp_path):
    database.configure(tmp_path / "test.db")
    await database.init_db()
    yield


# ── OnboardingStates ──────────────────────────────────────────────────────────

def test_onboarding_states_defined():
    from core.onboarding import OnboardingStates
    assert OnboardingStates.awaiting_name is not None
    assert OnboardingStates.awaiting_skill is not None
    assert OnboardingStates.awaiting_pdf is not None
    assert OnboardingStates.interview is not None


# ── parse_pdf ─────────────────────────────────────────────────────────────────

def test_parse_pdf_extracts_text(tmp_path):
    from core.onboarding import parse_pdf

    # Create a minimal real PDF with pypdf
    try:
        from pypdf import PdfWriter
    except ImportError:
        pytest.skip("pypdf not installed")

    pdf_path = tmp_path / "cv.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    # pypdf blank pages have no text — use mock instead
    with patch("pypdf.PdfReader") as mock_reader:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "John Doe\nSenior PM\n5 years experience"
        mock_reader.return_value.pages = [mock_page]
        result = parse_pdf(pdf_path)

    assert "John Doe" in result
    assert "Senior PM" in result


def test_parse_pdf_empty_raises(tmp_path):
    from core.onboarding import parse_pdf

    try:
        import pypdf  # noqa: F401
    except ImportError:
        pytest.skip("pypdf not installed")

    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"")

    with patch("pypdf.PdfReader") as mock_reader:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader.return_value.pages = [mock_page]
        with pytest.raises(ValueError, match="no text"):
            parse_pdf(pdf_path)


def test_parse_pdf_missing_pypdf(tmp_path):
    from core.onboarding import parse_pdf

    pdf_path = tmp_path / "cv.pdf"
    pdf_path.write_bytes(b"fake")

    with patch.dict("sys.modules", {"pypdf": None}):
        with pytest.raises(RuntimeError, match="pypdf not installed"):
            parse_pdf(pdf_path)


# ── synthesise_profile_stub ───────────────────────────────────────────────────

def test_synthesise_profile_stub_returns_valid_json():
    from core.onboarding import synthesise_profile_stub
    result = synthesise_profile_stub("CV text here", "Alex B", "pm")
    data = json.loads(result)
    assert data["name"] == "Alex B"
    assert data["skill_type"] == "pm"
    assert data["interview_completed"] is False
    assert "cv_raw" in data


def test_synthesise_profile_stub_truncates_long_cv():
    from core.onboarding import synthesise_profile_stub
    long_cv = "x" * 20_000
    result = synthesise_profile_stub(long_cv, "Test", "generic")
    data = json.loads(result)
    assert len(data["cv_raw"]) <= 10_000


# ── get_or_create_user_by_chat_id ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_or_create_creates_new_user():
    from core.onboarding import get_or_create_user_by_chat_id
    user_id = await get_or_create_user_by_chat_id(telegram_chat_id=555)
    assert isinstance(user_id, int)
    assert user_id > 0


@pytest.mark.asyncio
async def test_get_or_create_returns_same_id():
    from core.onboarding import get_or_create_user_by_chat_id
    uid1 = await get_or_create_user_by_chat_id(telegram_chat_id=777)
    uid2 = await get_or_create_user_by_chat_id(telegram_chat_id=777)
    assert uid1 == uid2


# ── DB helpers: update/get profile, onboarding_step ─────────────────────────

@pytest.mark.asyncio
async def test_update_and_get_profile():
    uid = await database.insert_user(name="Alex", skill_type="pm")
    await database.update_user_profile(uid, '{"name": "Alex"}')
    result = await database.get_user_profile(uid)
    assert result == '{"name": "Alex"}'


@pytest.mark.asyncio
async def test_get_profile_returns_none_before_set():
    uid = await database.insert_user(name="New User", skill_type="pm")
    result = await database.get_user_profile(uid)
    assert result is None


@pytest.mark.asyncio
async def test_update_onboarding_step():
    uid = await database.insert_user(name="User", skill_type="pm")
    await database.update_user_onboarding_step(uid, "awaiting_pdf")
    row = await database.get_user_by_id(uid)
    assert row["onboarding_step"] == "awaiting_pdf"


@pytest.mark.asyncio
async def test_clear_onboarding_step():
    uid = await database.insert_user(name="User", skill_type="pm")
    await database.update_user_onboarding_step(uid, "awaiting_pdf")
    await database.update_user_onboarding_step(uid, None)
    row = await database.get_user_by_id(uid)
    assert row["onboarding_step"] is None


# ── build_profile_from_cv ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_profile_persists_to_db():
    from tools.cv_onboard import build_profile_from_cv
    uid = await database.insert_user(name="", skill_type="pm")
    profile_json = await build_profile_from_cv(
        user_id=uid, name="Maria K", skill_type="generic", cv_text="CV content"
    )
    data = json.loads(profile_json)
    assert data["name"] == "Maria K"
    assert data["skill_type"] == "generic"

    stored = await database.get_user_profile(uid)
    assert stored == profile_json

    row = await database.get_user_by_id(uid)
    assert row["name"] == "Maria K"
    assert row["onboarding_step"] is None


# ── get_profile_for_llm ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_profile_returns_formatted_json():
    from tools.cv_onboard import get_profile_for_llm
    uid = await database.insert_user(name="Alex", skill_type="pm")
    await database.update_user_profile(uid, '{"name": "Alex"}')

    result = await get_profile_for_llm(uid)
    assert "# Candidate Profile" in result
    assert '"name": "Alex"' in result


@pytest.mark.asyncio
async def test_get_profile_fallback_when_empty():
    from tools.cv_onboard import get_profile_for_llm
    uid = await database.insert_user(name="Empty", skill_type="pm")

    result = await get_profile_for_llm(uid)
    assert "not yet created" in result
