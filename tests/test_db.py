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
