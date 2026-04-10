"""Planner presentation helpers."""

from __future__ import annotations

from mailops.agent.schemas import AskPlan
from mailops.core.policies import PolicyEngine


def explain_plan(plan: AskPlan) -> list[str]:
    """Summarize policy implications for a compiled plan."""

    engine = PolicyEngine()
    notes: list[str] = []
    for action in plan.actions:
        decision = engine.evaluate(action)
        if decision.requires_review:
            notes.append(f"{action.type.value} requires review: {decision.reason}")
        else:
            notes.append(f"{action.type.value} is low-risk: {decision.reason}")
    if not notes:
        notes.append("No actions were generated.")
    return notes

