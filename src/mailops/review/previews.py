"""Preview models for reviewable actions."""

from __future__ import annotations

from pydantic import BaseModel


class PreviewLine(BaseModel):
    description: str
    risk_note: str

