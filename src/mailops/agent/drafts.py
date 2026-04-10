"""Local draft proposal generation and batching."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re

from pydantic import BaseModel

from mailops.core.config import AppConfig
from mailops.index.db import (
    connect_db,
    create_action_proposal,
    create_audit_event,
    create_draft_proposal,
    create_review_batch,
    new_identifier,
)
from mailops.index.triage import refresh_thread_triage

GENERAL_STOPWORDS = {
    "all",
    "and",
    "ask",
    "client",
    "clients",
    "draft",
    "drafts",
    "day",
    "days",
    "email",
    "emails",
    "for",
    "from",
    "last",
    "messages",
    "month",
    "months",
    "note",
    "open",
    "past",
    "please",
    "previous",
    "proposal",
    "proposals",
    "queue",
    "recent",
    "replies",
    "reply",
    "show",
    "that",
    "the",
    "them",
    "these",
    "this",
    "thread",
    "threads",
    "within",
    "week",
    "year",
    "years",
}
SCHEDULING_TERMS = {"schedule", "scheduling", "calendar", "availability", "reschedule", "meeting", "invite"}
FINANCE_TERMS = {"invoice", "payment", "billing", "bill", "refund", "receipt", "vendor"}
DAY_WINDOW_RE = re.compile(r"(?P<count>\d+)\s+days?", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z][a-z0-9_-]+")


class DraftBatchResult(BaseModel):
    prompt: str
    batch_id: str | None = None
    matched_threads: int = 0
    proposals_created: int = 0
    reason: str


def create_draft_review_batch(config: AppConfig, prompt: str) -> DraftBatchResult:
    """Generate local draft proposals and a review batch from waiting-on-me threads."""

    refresh_thread_triage(config)
    lowered = prompt.strip().lower()
    since_days = _since_days_for_prompt(lowered)
    match_limit = 20 if "all" in lowered else 5
    topic = _topic_for_prompt(lowered)
    search_tokens = _search_tokens(lowered)

    with connect_db(config.db_path) as connection:
        candidates = _select_candidates(
            connection,
            since_days=since_days,
            topic=topic,
            search_tokens=search_tokens,
            limit=match_limit,
        )
        if not candidates:
            return DraftBatchResult(
                prompt=prompt,
                reason="No waiting-on-me threads matched the current draft request.",
            )

        created_at = datetime.now(timezone.utc).isoformat()
        batch_id = new_identifier("batch")
        create_review_batch(
            connection,
            batch_id=batch_id,
            batch_type="draft_queue",
            status="pending",
            scope_count=len(candidates),
            highest_risk="medium",
            reason=f"Local draft proposals created from '{prompt}'.",
            rollback_available=True,
            created_at=created_at,
        )

        for candidate in candidates:
            draft_id = new_identifier("draft")
            action_id = new_identifier("action")
            draft = _build_local_draft(candidate)
            create_draft_proposal(
                connection,
                proposal_id=draft_id,
                thread_id=str(candidate["thread_id"]),
                style_profile=draft["style_profile"],
                proposed_subject=draft["subject"],
                proposed_body=draft["body"],
                confidence=draft["confidence"],
                rationale=draft["rationale"],
                created_at=created_at,
            )
            create_action_proposal(
                connection,
                proposal_id=action_id,
                batch_id=batch_id,
                action_type="create_draft",
                scope=[str(candidate["thread_id"])],
                reason=draft["action_reason"],
                evidence_refs=list(candidate["classification_tags"])[:4],
                draft_proposal_id=draft_id,
                risk_level="medium",
                review_status="pending",
                execution_status="pending",
                created_at=created_at,
            )

        create_audit_event(
            connection,
            event_id=new_identifier("audit"),
            actor="mailops.ask",
            action_type="draft_batch_created",
            target_ref=batch_id,
            timestamp=created_at,
            result="pending_review",
            after_state={
                "matched_threads": len(candidates),
                "topic": topic,
                "since_days": since_days,
            },
        )

    return DraftBatchResult(
        prompt=prompt,
        batch_id=batch_id,
        matched_threads=len(candidates),
        proposals_created=len(candidates),
        reason=f"Prepared {len(candidates)} local draft proposals for review.",
    )


def _select_candidates(
    connection: object,
    *,
    since_days: int,
    topic: str,
    search_tokens: set[str],
    limit: int,
) -> list[dict[str, object]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    rows = connection.execute(
        """
        SELECT
            threads.id AS thread_id,
            threads.account_id AS account_id,
            threads.subject AS subject,
            threads.last_message_at AS last_message_at,
            threads.importance_score AS importance_score,
            threads.classification_tags AS classification_tags,
            messages.sender AS sender,
            messages.body_text AS body_text,
            messages.snippet AS snippet
        FROM threads
        JOIN messages
          ON messages.id = (
              SELECT candidate.id
              FROM messages AS candidate
              WHERE candidate.thread_id = threads.id
              ORDER BY COALESCE(candidate.received_at, candidate.sent_at, '') DESC
              LIMIT 1
          )
        WHERE threads.followup_state = 'waiting_on_me'
          AND threads.last_message_at IS NOT NULL
          AND threads.last_message_at >= ?
        ORDER BY threads.importance_score DESC, threads.last_message_at DESC
        """,
        (cutoff,),
    ).fetchall()

    selected: list[dict[str, object]] = []
    for row in rows:
        candidate = {
            "thread_id": str(row["thread_id"]),
            "account_id": str(row["account_id"]),
            "subject": str(row["subject"]),
            "last_message_at": str(row["last_message_at"]),
            "importance_score": float(row["importance_score"]),
            "classification_tags": _json_list(row["classification_tags"]),
            "sender": str(row["sender"]),
            "body_text": str(row["body_text"]),
            "snippet": str(row["snippet"]),
        }
        if not _matches_topic(candidate, topic=topic, search_tokens=search_tokens):
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def _matches_topic(candidate: dict[str, object], *, topic: str, search_tokens: set[str]) -> bool:
    haystack = " ".join(
        [
            str(candidate["subject"]).lower(),
            str(candidate["body_text"]).lower(),
            str(candidate["snippet"]).lower(),
            " ".join(str(item).lower() for item in candidate["classification_tags"]),
        ]
    )
    if topic == "scheduling" and not any(term in haystack for term in SCHEDULING_TERMS):
        return False
    if topic == "finance" and not any(term in haystack for term in FINANCE_TERMS):
        return False
    if not search_tokens:
        return True
    return any(token in haystack for token in search_tokens)


def _build_local_draft(candidate: dict[str, object]) -> dict[str, object]:
    subject = str(candidate["subject"])
    sender = str(candidate["sender"])
    reasons = list(candidate["classification_tags"])
    body_text = str(candidate["body_text"]).lower()

    if any(term in body_text or term in subject.lower() for term in SCHEDULING_TERMS):
        style_profile = "scheduling"
        template_line = "I can coordinate on my side. Please send two or three times that work best for you, and I will confirm the best option."
    elif any(term in body_text or term in subject.lower() for term in FINANCE_TERMS):
        style_profile = "finance"
        template_line = "I am reviewing the invoice and payment details now and will confirm the next step shortly."
    else:
        style_profile = "follow_up"
        template_line = "I reviewed your note and will follow up with a concrete update shortly."

    recipient_name = _friendly_name(sender)
    proposal_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    confidence = min(0.95, round(0.55 + float(candidate["importance_score"]) * 0.35 + 0.05, 2))
    rationale = (
        f"Generated from a {style_profile.replace('_', ' ')} thread scored at {float(candidate['importance_score']):.0%}. "
        f"Signals: {', '.join(reasons[:3]) or 'waiting_on_me'}."
    )
    action_reason = (
        f"Create a provider draft from local proposal for thread '{subject}' after operator review."
    )
    body = "\n".join(
        [
            f"Hi {recipient_name},",
            "",
            "Thanks for the follow-up.",
            template_line,
            "",
            "Best,",
            "[Your Name]",
        ]
    )
    return {
        "style_profile": style_profile,
        "subject": proposal_subject,
        "body": body,
        "confidence": confidence,
        "rationale": rationale,
        "action_reason": action_reason,
    }


def _friendly_name(sender: str) -> str:
    local_part = sender.split("@", 1)[0].replace(".", " ").replace("_", " ").replace("-", " ")
    tokens = [token for token in local_part.split() if token]
    if not tokens:
        return "there"
    return tokens[0].capitalize()


def _since_days_for_prompt(prompt: str) -> int:
    if "today" in prompt:
        return 1
    if "this week" in prompt:
        return 7
    if "this month" in prompt:
        return 31
    match = DAY_WINDOW_RE.search(prompt)
    if match is not None:
        return int(match.group("count"))
    return 14


def _topic_for_prompt(prompt: str) -> str:
    if any(term in prompt for term in SCHEDULING_TERMS):
        return "scheduling"
    if any(term in prompt for term in FINANCE_TERMS):
        return "finance"
    return "general"


def _search_tokens(prompt: str) -> set[str]:
    return {
        token
        for token in TOKEN_RE.findall(prompt)
        if token not in GENERAL_STOPWORDS and len(token) > 2
    }


def _json_list(raw_value: object) -> list[str]:
    if raw_value in (None, ""):
        return []
    return [str(item) for item in json.loads(str(raw_value))]
