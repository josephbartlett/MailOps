"""Simple planner that compiles natural-language requests into explicit actions."""

from __future__ import annotations

from mailops.agent.schemas import AskPlan
from mailops.core.actions import ActionRequest, ActionType
from mailops.core.models import RiskTier


def compile_request(prompt: str) -> AskPlan:
    """Produce a small structured plan from a user request."""

    lowered = prompt.lower()

    if any(token in lowered for token in ("rule", "filter", "sieve")):
        return AskPlan(
            request=prompt,
            intent="rule_generation",
            summary="Generate provider-native rule proposals and keep them review-first.",
            actions=[
                ActionRequest(
                    type=ActionType.PROPOSE_RULE,
                    reason="Rule proposals are medium risk until preview and approval happen.",
                    risk_level=RiskTier.MEDIUM,
                )
            ],
        )

    if any(token in lowered for token in ("draft", "reply", "respond")):
        return AskPlan(
            request=prompt,
            intent="draft_queue",
            summary="Prepare local draft proposals for operator review.",
            actions=[
                ActionRequest(
                    type=ActionType.CREATE_DRAFT,
                    reason="Draft generation is medium risk because it creates provider-adjacent content for review.",
                    risk_level=RiskTier.MEDIUM,
                )
            ],
        )

    if any(token in lowered for token in ("archive", "move", "label", "bulk")):
        return AskPlan(
            request=prompt,
            intent="bulk_review",
            summary="Compile the request into a review batch before any mailbox mutation.",
            actions=[
                ActionRequest(
                    type=ActionType.ARCHIVE_THREAD,
                    reason="Bulk mailbox mutations are high risk and always require review.",
                    risk_level=RiskTier.HIGH,
                )
            ],
        )

    if any(token in lowered for token in ("unanswered", "follow-up", "follow up", "waiting")):
        return AskPlan(
            request=prompt,
            intent="followup_analysis",
            summary="Query local thread state and rank likely follow-up candidates.",
            actions=[
                ActionRequest(
                    type=ActionType.CLASSIFY,
                    reason="Follow-up classification is a low-risk local analysis task.",
                    risk_level=RiskTier.LOW,
                )
            ],
        )

    return AskPlan(
        request=prompt,
        intent="triage_query",
        summary="Inspect local mailbox state and return an operator-facing summary.",
        actions=[
            ActionRequest(
                type=ActionType.SUMMARIZE,
                reason="General triage queries are low-risk read-only operations.",
                risk_level=RiskTier.LOW,
            )
        ],
    )
