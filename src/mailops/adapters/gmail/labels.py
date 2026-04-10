"""Gmail label placeholder."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GmailLabelMutation(BaseModel):
    thread_id: str
    add_labels: list[str] = Field(default_factory=list)
    remove_labels: list[str] = Field(default_factory=list)
