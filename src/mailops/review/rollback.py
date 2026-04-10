"""Rollback primitives."""

from __future__ import annotations

from pydantic import BaseModel


class RollbackPlan(BaseModel):
    batch_id: str
    supported: bool
    reason: str

