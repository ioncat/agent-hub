"""
tests/test_db.py — contract tests for db/database.py.

Run: python -m pytest tests/test_db.py -v
Uses a temporary DB file, cleaned up after each test.
"""

import pytest
import pytest_asyncio

from db import database


@pytest_asyncio.fixture(autouse=True)
async def temp_db(tmp_path):
    """Point database module at a fresh temp DB for each test."""
    database.configure(tmp_path / "test.db")
    await database.init_db()
    yield
    # cleanup handled by tmp_path fixture


# ── init_db ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_init_db_idempotent():
    """init_db() can be called twice without error."""
    await database.init_db()  # second call


# ── vacancies ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_insert_and_get_vacancy():
    vid = await database.insert_vacancy(
        url="https://djinni.co/jobs/123/",
        title="Backend Dev",
        site="djinni",
        markdown_path="vacancies/djinni/job-123/JD.md",
    )
    assert isinstance(vid, int)
    assert vid > 0

    row = await database.get_vacancy_by_url("https://djinni.co/jobs/123/")
    assert row is not None
    assert row["title"] == "Backend Dev"
    assert row["site"] == "djinni"
    assert row["status"] == "fetched"


@pytest.mark.asyncio
async def test_get_vacancy_by_id():
    vid = await database.insert_vacancy(url="https://djinni.co/jobs/456/")
    row = await database.get_vacancy_by_id(vid)
    assert row is not None
    assert row["url"] == "https://djinni.co/jobs/456/"


@pytest.mark.asyncio
async def test_get_vacancy_not_found():
    row = await database.get_vacancy_by_url("https://example.com/not-there")
    assert row is None


@pytest.mark.asyncio
async def test_update_vacancy_status():
    vid = await database.insert_vacancy(url="https://djinni.co/jobs/789/")
    await database.update_vacancy_status(vid, "analyzing")

    row = await database.get_vacancy_by_id(vid)
    assert row["status"] == "analyzing"


@pytest.mark.asyncio
async def test_list_vacancies():
    await database.insert_vacancy(url="https://djinni.co/jobs/1/")
    await database.insert_vacancy(url="https://djinni.co/jobs/2/")
    rows = await database.list_vacancies()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_list_vacancies_filter_status():
    vid = await database.insert_vacancy(url="https://djinni.co/jobs/10/")
    await database.update_vacancy_status(vid, "done")
    await database.insert_vacancy(url="https://djinni.co/jobs/11/")  # stays 'fetched'

    done = await database.list_vacancies(status="done")
    assert len(done) == 1
    assert done[0]["url"] == "https://djinni.co/jobs/10/"


# ── pipeline_runs ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_insert_pipeline_run():
    vid = await database.insert_vacancy(url="https://djinni.co/jobs/20/")
    run_id = await database.insert_pipeline_run(vid, "phase1")
    assert isinstance(run_id, int)


@pytest.mark.asyncio
async def test_update_pipeline_run_done():
    vid = await database.insert_vacancy(url="https://djinni.co/jobs/21/")
    run_id = await database.insert_pipeline_run(vid, "phase1")

    await database.update_pipeline_run(run_id, "running")
    await database.update_pipeline_run(run_id, "done", result_path="vacancies/job-21/analysis.md")

    runs = await database.get_pipeline_runs(vid)
    assert len(runs) == 1
    assert runs[0]["status"] == "done"
    assert runs[0]["result_path"] == "vacancies/job-21/analysis.md"
    assert runs[0]["finished_at"] is not None


@pytest.mark.asyncio
async def test_update_pipeline_run_error():
    vid = await database.insert_vacancy(url="https://djinni.co/jobs/22/")
    run_id = await database.insert_pipeline_run(vid, "phase2")

    await database.update_pipeline_run(run_id, "error", error_message="Claude API timeout")

    runs = await database.get_pipeline_runs(vid)
    assert runs[0]["status"] == "error"
    assert "timeout" in runs[0]["error_message"]


# ── users ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_insert_and_get_user_by_id():
    uid = await database.insert_user(name="Alex Bondarenko", telegram_chat_id=123456, skill_type="pm")
    assert isinstance(uid, int)
    assert uid > 0

    row = await database.get_user_by_id(uid)
    assert row is not None
    assert row["name"] == "Alex Bondarenko"
    assert row["telegram_chat_id"] == 123456
    assert row["skill_type"] == "pm"


@pytest.mark.asyncio
async def test_get_user_by_telegram_id():
    await database.insert_user(name="Maria Beleshko", telegram_chat_id=999888, skill_type="generic")
    row = await database.get_user_by_telegram_id(999888)
    assert row is not None
    assert row["name"] == "Maria Beleshko"
    assert row["skill_type"] == "generic"


@pytest.mark.asyncio
async def test_get_user_not_found():
    row = await database.get_user_by_id(9999)
    assert row is None

    row2 = await database.get_user_by_telegram_id(0)
    assert row2 is None


@pytest.mark.asyncio
async def test_get_or_create_default_user_creates_new():
    uid = await database.get_or_create_default_user(telegram_chat_id=111222, name="New User", skill_type="pm")
    assert isinstance(uid, int)
    row = await database.get_user_by_id(uid)
    assert row["name"] == "New User"


@pytest.mark.asyncio
async def test_get_or_create_default_user_returns_existing():
    uid1 = await database.get_or_create_default_user(telegram_chat_id=333444, name="Existing", skill_type="pm")
    uid2 = await database.get_or_create_default_user(telegram_chat_id=333444, name="Existing", skill_type="pm")
    assert uid1 == uid2  # idempotent — same user returned


@pytest.mark.asyncio
async def test_list_users():
    await database.insert_user(name="User A", telegram_chat_id=1001, skill_type="pm")
    await database.insert_user(name="User B", telegram_chat_id=1002, skill_type="generic")
    users = await database.list_users()
    assert len(users) == 2
    assert users[0]["name"] == "User A"
    assert users[1]["skill_type"] == "generic"


@pytest.mark.asyncio
async def test_update_user_skill_type():
    uid = await database.insert_user(name="Switch User", telegram_chat_id=5555, skill_type="pm")
    await database.update_user_skill_type(uid, "generic")
    row = await database.get_user_by_id(uid)
    assert row["skill_type"] == "generic"


@pytest.mark.asyncio
async def test_user_telegram_id_unique_constraint():
    """Duplicate telegram_chat_id must raise IntegrityError."""
    import sqlite3
    await database.insert_user(name="First", telegram_chat_id=77777)
    with pytest.raises(Exception):  # sqlite3.IntegrityError wrapped by aiosqlite
        await database.insert_user(name="Duplicate", telegram_chat_id=77777)


# ── user_id FK — vacancies & llm_usage ───────────────────────────────────────

@pytest.mark.asyncio
async def test_insert_vacancy_with_user_id():
    uid = await database.insert_user(name="Alex", telegram_chat_id=11111, skill_type="pm")
    vid = await database.insert_vacancy(url="https://djinni.co/jobs/100/", user_id=uid)

    row = await database.get_vacancy_by_id(vid)
    assert row["user_id"] == uid


@pytest.mark.asyncio
async def test_insert_vacancy_without_user_id_is_null():
    """Backward compat: vacancy without user_id inserts fine, user_id=NULL."""
    vid = await database.insert_vacancy(url="https://djinni.co/jobs/200/")
    row = await database.get_vacancy_by_id(vid)
    assert row["user_id"] is None


@pytest.mark.asyncio
async def test_list_vacancies_filter_by_user_id():
    uid1 = await database.insert_user(name="User1", telegram_chat_id=22221, skill_type="pm")
    uid2 = await database.insert_user(name="User2", telegram_chat_id=22222, skill_type="generic")

    await database.insert_vacancy(url="https://djinni.co/jobs/300/", user_id=uid1)
    await database.insert_vacancy(url="https://djinni.co/jobs/301/", user_id=uid1)
    await database.insert_vacancy(url="https://djinni.co/jobs/302/", user_id=uid2)

    rows1 = await database.list_vacancies(user_id=uid1)
    rows2 = await database.list_vacancies(user_id=uid2)
    all_rows = await database.list_vacancies()

    assert len(rows1) == 2
    assert len(rows2) == 1
    assert len(all_rows) == 3


@pytest.mark.asyncio
async def test_list_vacancies_filter_status_and_user_id():
    uid = await database.insert_user(name="User3", telegram_chat_id=33331, skill_type="pm")
    vid = await database.insert_vacancy(url="https://djinni.co/jobs/400/", user_id=uid)
    await database.update_vacancy_status(vid, "done")
    await database.insert_vacancy(url="https://djinni.co/jobs/401/", user_id=uid)  # stays fetched

    done = await database.list_vacancies(status="done", user_id=uid)
    assert len(done) == 1
    assert done[0]["url"] == "https://djinni.co/jobs/400/"


@pytest.mark.asyncio
async def test_insert_llm_usage_with_user_id():
    uid = await database.insert_user(name="Alex", telegram_chat_id=44441, skill_type="pm")
    vid = await database.insert_vacancy(url="https://djinni.co/jobs/500/", user_id=uid)

    row_id = await database.insert_llm_usage(
        phase="phase1",
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=200,
        cache_write_tokens=0,
        cache_read_tokens=0,
        cost_usd=0.001,
        vacancy_id=vid,
        user_id=uid,
    )
    assert isinstance(row_id, int)
    assert row_id > 0
