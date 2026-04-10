"""Action schemas and risk-bearing requests."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from mailops.core.models import RiskTier


class ActionType(str, Enum):
    SUMMARIZE = "summarize"
    CLASSIFY = "classify"
    CREATE_DRAFT = "create_draft"
    LABEL_THREAD = "label_thread"
    MOVE_THREAD = "move_thread"
    ARCHIVE_THREAD = "archive_thread"
    SEND_MESSAGE = "send_message"
    DELETE_MESSAGE = "delete_message"
    PROPOSE_RULE = "propose_rule"
    APPLY_PROVIDER_RULE = "apply_provider_rule"


class ActionRequest(BaseModel):
    """Structured action request emitted by the planner or review flow."""

    type: ActionType
    scope: list[str] = Field(default_factory=list)
    reason: str
    risk_level: RiskTier
    evidence: list[str] = Field(default_factory=list)


class ActionPreview(BaseModel):
    """Operator-facing preview for a proposed action."""

    action: ActionRequest
    user_visible_effect: str
    rollback_available: bool = False

