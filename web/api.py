"""
web/api.py — FastAPI web tracker: read-only view of vacancy pipeline state.

Standalone: uvicorn web.api:app --reload
Does not require ANTHROPIC_API_KEY or TELEGRAM_BOT_TOKEN.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import markdown as md_lib
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from db import database
from web.reader import build_vacancy_view

log = logging.getLogger(__name__)

_DB_PATH = Path(os.getenv("DB_PATH", "db/agent.db"))
_CANDIDATE_NAME = os.getenv("CANDIDATE_NAME", "Candidate")

_TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")
_TEMPLATES.env.filters["markdown"] = lambda text: md_lib.markdown(
    text or "", extensions=["tables", "fenced_code"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.configure(_DB_PATH)
    await database.init_db()
    yield


app = FastAPI(title="Career Agent Tracker", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def tracker_page(
    request: Request,
    status: str | None = None,
    user_id: int | None = None,
    limit: int = 200,
):
    rows = await database.list_vacancies(status=status, user_id=user_id, limit=limit)
    vacancies = [build_vacancy_view(row, _CANDIDATE_NAME) for row in rows]
    users = await database.list_users()
    return _TEMPLATES.TemplateResponse(
        request=request,
        name="tracker.html",
        context={
            "vacancies": vacancies,
            "total": len(vacancies),
            "users": [dict(u) for u in users],
            "selected_user_id": user_id,
        },
    )


@app.get("/api/vacancies")
async def api_vacancies(
    status: str | None = None,
    user_id: int | None = None,
    limit: int = 200,
):
    rows = await database.list_vacancies(status=status, user_id=user_id, limit=limit)
    return [dict(row) for row in rows]


@app.get("/api/users")
async def api_users():
    rows = await database.list_users()
    return [dict(row) for row in rows]


class NewVacancyRequest(BaseModel):
    url: str
    title: str | None = None
    feed_name: str | None = None
    user_id: int | None = None


@app.post("/api/new-vacancy", status_code=201)
async def api_new_vacancy(req: NewVacancyRequest):
    """Webhook endpoint for job-monitor: queue a new vacancy for fetching.

    Returns 201 on success, 409 if URL already exists in DB.
    career-agent's RSSWatcher polls for status='queued' and triggers cv_fetch_jd.
    """
    existing = await database.get_vacancy_by_url(req.url)
    if existing is not None:
        raise HTTPException(status_code=409, detail="duplicate")
    try:
        vacancy_id = await database.insert_vacancy(
            url=req.url,
            title=req.title,
            user_id=req.user_id,
            status="queued",
        )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="duplicate")
        raise
    log.info("api/new-vacancy: queued vacancy_id=%d url=%s", vacancy_id, req.url)
    return {"vacancy_id": vacancy_id, "status": "queued"}


@app.get("/api/vacancies/{vacancy_id}")
async def api_vacancy(vacancy_id: int):
    row = await database.get_vacancy_by_id(vacancy_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return dict(row)
