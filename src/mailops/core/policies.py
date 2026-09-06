"""Policy engine shell."""

from __future__ import annotations

from pydantic import BaseModel

from mailops.core.actions import ActionRequest, ActionType
from mailops.core.models import RiskTier


class PolicyDecision(BaseModel):
    """Outcome of evaluating an action against local policy."""

    allowed: bool
    requires_review: bool
    reason: str


class PolicyEngine:
    """Minimal v1 policy gate with explicit risk semantics."""

    def evaluate(self, action: ActionRequest) -> PolicyDecision:
        risk = effective_risk(action.type, action.risk_level)
        if risk == RiskTier.HIGH:
            return PolicyDecision(
                allowed=False,
                requires_review=True,
                reason="High-risk actions remain blocked by default until explicit review and execution support exist.",
            )
        if risk == RiskTier.MEDIUM:
            return PolicyDecision(
                allowed=False,
                requires_review=True,
                reason="Medium-risk actions are review-first in the current milestone.",
            )
        return PolicyDecision(
            allowed=True,
            requires_review=False,
            reason="Low-risk actions may execute automatically once the execution layer is implemented.",
        )


def effective_risk(action_type: str, declared_risk: RiskTier) -> RiskTier:
    """Enforce action-specific risk floors regardless of planner input."""

    floors = {
        ActionType.SUMMARIZE: RiskTier.LOW,
        ActionType.CLASSIFY: RiskTier.LOW,
        ActionType.CREATE_DRAFT: RiskTier.MEDIUM,
        ActionType.PROPOSE_RULE: RiskTier.MEDIUM,
    }
    floor = floors.get(action_type, RiskTier.HIGH)
    levels = {RiskTier.LOW: 0, RiskTier.MEDIUM: 1, RiskTier.HIGH: 2}
    return max((floor, declared_risk), key=levels.__getitem__)
