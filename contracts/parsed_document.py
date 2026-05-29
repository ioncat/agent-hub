"""
contracts/parsed_document.py — shared contract for kmp-service /parse response.

Mirrors the ParsedDocument model in knowledge-mirror-parser/api.py.
Both sides must stay in sync — if kmp response changes, update here.
"""

from pydantic import BaseModel, HttpUrl


class ParsedDocument(BaseModel):
    """Clean-parsed job description returned by kmp-service POST /parse."""

    title: str
    markdown: str
    source_url: str

    @property
    def is_empty(self) -> bool:
        return not self.markdown.strip()
