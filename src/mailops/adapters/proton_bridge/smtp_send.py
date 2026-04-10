"""SMTP send primitives for Proton Bridge."""

from __future__ import annotations

from pydantic import BaseModel


class SendRequest(BaseModel):
    account_id: str
    draft_id: str


class SendResult(BaseModel):
    accepted: bool
    message: str

