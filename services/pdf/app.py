"""
services/pdf/app.py — PDF render service.

POST /render  {"markdown": str} → application/pdf
GET  /health  → {"status": "ok"}

Run:
    uvicorn services.pdf.app:app --port 8002
    # or inside Docker: uvicorn app:app --host 0.0.0.0 --port 8002
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from render import render_to_bytes

app = FastAPI(title="Career Agent PDF Service", version="1.0.0")


class RenderRequest(BaseModel):
    markdown: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/render")
def render(req: RenderRequest) -> Response:
    """Render markdown to PDF. Returns raw PDF bytes (application/pdf)."""
    if not req.markdown.strip():
        raise HTTPException(status_code=422, detail="markdown field is empty")
    try:
        pdf_bytes = render_to_bytes(req.markdown)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Render error: {exc}") from exc
    return Response(content=pdf_bytes, media_type="application/pdf")
