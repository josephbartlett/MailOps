import pytest

from mailops.core.actions import ActionRequest, ActionType
from mailops.core.models import RiskTier
from mailops.core.policies import PolicyEngine


@pytest.mark.parametrize("action_type", [
    ActionType.SEND_MESSAGE, ActionType.DELETE_MESSAGE, ActionType.ARCHIVE_THREAD,
    ActionType.MOVE_THREAD, ActionType.LABEL_THREAD, ActionType.APPLY_PROVIDER_RULE,
    ActionType.CREATE_DRAFT, ActionType.PROPOSE_RULE,
])
def test_mutating_actions_cannot_bypass_policy_by_claiming_low_risk(action_type):
    decision = PolicyEngine().evaluate(ActionRequest(
        type=action_type, reason="Planner supplied a misleading risk", risk_level=RiskTier.LOW,
    ))
    assert not decision.allowed
    assert decision.requires_review


@pytest.mark.parametrize("action_type", [ActionType.SUMMARIZE, ActionType.CLASSIFY])
def test_local_analysis_remains_allowed(action_type):
    assert PolicyEngine().evaluate(ActionRequest(
        type=action_type, reason="Local analysis", risk_level=RiskTier.LOW,
    )).allowed
