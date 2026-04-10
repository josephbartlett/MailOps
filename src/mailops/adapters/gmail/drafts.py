"""Gmail draft placeholder."""

from __future__ import annotations

from pydantic import BaseModel


class GmailDraftRequest(BaseModel):
    thread_id: str
    subject: str
    body: str

