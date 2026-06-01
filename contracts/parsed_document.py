"""
contracts/parsed_document.py — shared contract for jd-parser /parse response.

Mirrors the ParsedDocument model in services/parser/app.py.
Both sides must stay in sync — if parser response changes, update here.
"""

from pydantic import BaseModel, HttpUrl


class ParsedDocument(BaseModel):
    """Clean-parsed job description returned by jd-parser POST /parse."""

    title: str
    markdown: str
    source_url: str

    @property
    def is_empty(self) -> bool:
        return not self.markdown.strip()
