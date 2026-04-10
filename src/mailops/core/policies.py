"""Policy engine shell."""

from __future__ import annotations

from pydantic import BaseModel

from mailops.core.actions import ActionRequest
from mailops.core.models import RiskTier


class PolicyDecision(BaseModel):
    """Outcome of evaluating an action against local policy."""

    allowed: bool
    requires_review: bool
    reason: str


class PolicyEngine:
    """Minimal v1 policy gate with explicit risk semantics."""

    def evaluate(self, action: ActionRequest) -> PolicyDecision:
        if action.risk_level == RiskTier.HIGH:
            return PolicyDecision(
                allowed=False,
                requires_review=True,
                reason="High-risk actions remain blocked by default until explicit review and execution support exist.",
            )
        if action.risk_level == RiskTier.MEDIUM:
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
