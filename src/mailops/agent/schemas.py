"""Planner-facing schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from mailops.core.actions import ActionRequest


class AskPlan(BaseModel):
    request: str
    intent: str
    summary: str
    actions: list[ActionRequest] = Field(default_factory=list)

