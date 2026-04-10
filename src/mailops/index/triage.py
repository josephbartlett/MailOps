"""Thread-level follow-up classification and triage scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
import sqlite3
from typing import Iterable, Sequence

from mailops.core.config import AppConfig
from mailops.index.db import connect_db, initialize_database

AUTOMATED_LOCAL_PARTS = (
    "do-not-reply",
    "donotreply",
    "no-reply",
    "noreply",
    "notifications",
    "notification",
    "updates",
    "digest",
    "newsletter",
    "mailer-daemon",
)
AUTOMATED_SUBJECT_HINTS = (
    "[github]",
    "newsletter",
    "digest",
    "notification",
    "receipt",
)
BROADCAST_HINTS = (
    "and more |",
    "newsletter",
    "digest",
    "webinar",
    "workshop",
    "forum",
    "conference",
    "summit",
    "resources",
    "save money",
    "early-bird",
    "early bird",
    "edition",
)
SECURITY_INFO_HINTS = (
    "your device has been registered",
    "new sign-in",
    "new login",
    "security alert",
    "verification code",
    "password reset",
)
PASSIVE_UPDATE_HINTS = (
    "submission confirmation",
    "confirm that",
    "submitting your resume",
    "submitted your resume",
    "hiring manager",
    "once we hear",
    "we will be in touch",
    "we will follow up",
    "for your review",
    "thank you for your time",
)
COLD_OUTREACH_HINTS = (
    "worth a chat",
    "wanted to reach out",
    "came across",
    "working with other",
    "if you don't want to hear from me again",
    "if you do not want to hear from me again",
    "quick chat",
    "potential mutual fit",
)
STAFFING_DOMAIN_HINTS = (
    "recruit",
    "staff",
    "talent",
    "placement",
    "headhunt",
)
RECRUITER_TITLE_HINTS = (
    "recruiter",
    "recruiting specialist",
    "technical recruiter",
    "talent acquisition",
    "account manager",
    "staffing",
)
RECRUITING_OUTREACH_HINTS = (
    "open role",
    "open position",
    "opportunity",
    "updated resume",
    "share your resume",
    "share your updated resume",
    "new opportunity",
    "further process",
)
RECRUITING_PROCESS_HINTS = (
    "submission confirmation",
    "submitting your resume",
    "hiring manager",
    "client name:",
    "pay rate",
    "w2",
    "availability:",
    "duration:",
)
LOGISTICS_HINTS = (
    "shipping label",
    "equipment return",
    "return equipment",
    "return your laptop",
    "return your equipment",
    "return label",
    "contractors no longer with",
)
CALENDAR_INVITE_HINTS = (
    "invitation:",
    "updated invitation:",
    "icaluid",
    "calendar invitation",
    "accepted:",
    "declined:",
    "tentative:",
)
URGENT_HINTS = (
    "urgent",
    "asap",
    "follow up",
    "follow-up",
    "deadline",
)
FINANCE_HINTS = (
    "invoice",
    "payment",
    "paid",
    "billing",
    "bill",
    "refund",
    "receipt",
)
SCHEDULING_HINTS = (
    "schedule",
    "scheduling",
    "calendar",
    "availability",
    "reschedule",
    "meeting",
)
QUESTION_HINTS = (
    "can you",
    "could you",
    "would you",
    "let me know",
    "please let me know",
    "please confirm",
    "please review",
    "please share",
    "work for you",
    "when would you",
    "would tomorrow",
    "when works",
    "what works",
)
RESOLVED_HINTS = (
    "thanks",
    "thank you",
    "sounds good",
    "looks good",
    "resolved",
    "done",
    "all set",
    "paid",
    "works for me",
    "see you then",
)
QUESTION_RE = re.compile(
    r"(\b(can|could|would|will|are)\s+you\b[^?]{0,120}\?|\bwhen\b[^?]{0,60}\?|\bwork for you\b[^?]{0,40}\?)",
    re.IGNORECASE,
)
QUOTE_MARKERS = (
    "\n-----original message-----",
    "\nfrom:",
    "\non ",
    "\n> ",
)
QUOTE_PATTERNS = (
    re.compile(r"\bon\s+[a-z]{3},?\s+.+?\bwrote:", re.IGNORECASE),
    re.compile(r"-{2,}\s*original message\s*-{2,}", re.IGNORECASE),
)


@dataclass(frozen=True)
class ThreadMessageSnapshot:
    sender: str
    to_recipients: list[str]
    cc_recipients: list[str]
    bcc_recipients: list[str]
    sent_at: datetime | None
    received_at: datetime | None
    snippet: str
    body_text: str
    flags: list[str]

    @property
    def event_at(self) -> datetime:
        if self.received_at is not None:
            return self.received_at
        if self.sent_at is not None:
            return self.sent_at
        return datetime.min.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class ThreadTriageAssessment:
    last_message_at: str | None
    unread_count: int
    importance_score: float
    followup_state: str
    participants: list[str]
    classification_tags: list[str]


def assess_thread(
    *,
    subject: str,
    account_aliases: set[str],
    messages: Sequence[ThreadMessageSnapshot],
    now: datetime | None = None,
) -> ThreadTriageAssessment:
    """Classify a thread and derive a transparent triage score."""

    if not messages:
        return ThreadTriageAssessment(
            last_message_at=None,
            unread_count=0,
            importance_score=0.0,
            followup_state="ambiguous",
            participants=[],
            classification_tags=["no messages synced"],
        )

    current_time = now or datetime.now(timezone.utc)
    ordered = sorted(messages, key=lambda item: item.event_at)
    last_message = ordered[-1]
    all_participants = sorted(
        {
            participant
            for message in ordered
            for participant in (message.sender, *message.to_recipients, *message.cc_recipients, *message.bcc_recipients)
            if participant
        }
    )
    external_participants = {participant for participant in all_participants if participant not in account_aliases}
    last_sender_is_me = last_message.sender in account_aliases
    prior_outbound = any(message.sender in account_aliases for message in ordered[:-1])
    unread_inbound_count = sum(
        1
        for message in ordered
        if message.sender not in account_aliases and not _has_seen_flag(message.flags)
    )

    analysis_body = _extract_recent_body(last_message.body_text)
    last_text = _normalized_text(subject, last_message.snippet, analysis_body)
    direct_to_me = any(address in account_aliases for address in last_message.to_recipients)
    cc_to_me = any(address in account_aliases for address in last_message.cc_recipients)
    urgent = _contains_any(last_text, URGENT_HINTS)
    finance = _contains_any(last_text, FINANCE_HINTS)
    scheduling = _contains_any(last_text, SCHEDULING_HINTS)
    body_text = _normalized_text(analysis_body)
    question = _contains_any(body_text, QUESTION_HINTS) or QUESTION_RE.search(body_text) is not None
    resolved_hint = _contains_any(last_text, RESOLVED_HINTS) and not question
    automated = _looks_automated_sender(last_message.sender) or _contains_any(last_text, AUTOMATED_SUBJECT_HINTS)
    broadcast = _contains_any(last_text, BROADCAST_HINTS) or ("|" in subject and len(ordered) == 1)
    security_info = _contains_any(last_text, SECURITY_INFO_HINTS)
    passive_update = _contains_any(last_text, PASSIVE_UPDATE_HINTS)
    cold_outreach = _contains_any(last_text, COLD_OUTREACH_HINTS)
    sender_domain = _sender_domain(last_message.sender)
    recruiter_sender = _contains_any(last_text, RECRUITER_TITLE_HINTS) or _contains_any(
        sender_domain, STAFFING_DOMAIN_HINTS
    )
    recruiting_process = recruiter_sender and _contains_any(last_text, RECRUITING_PROCESS_HINTS)
    recruiter_outreach = not recruiting_process and (
        _contains_any(last_text, RECRUITING_OUTREACH_HINTS)
        or (recruiter_sender and ("role" in subject.lower() or "resume" in body_text))
    )
    logistics_request = _contains_any(last_text, LOGISTICS_HINTS)
    calendar_invite = subject.lower().startswith(("invitation:", "updated invitation:")) or _contains_any(
        last_text, CALENDAR_INVITE_HINTS
    )
    stale_days = max(0, int((current_time - last_message.event_at) / timedelta(days=1)))
    direct_request = question
    dormant_single_inbound = len(ordered) == 1 and not last_sender_is_me and unread_inbound_count == 0 and stale_days > 90

    reasons: list[str] = []
    if last_sender_is_me:
        reasons.append("latest message from you")
    else:
        reasons.append("latest message from external sender")
    if unread_inbound_count:
        reasons.append("unread inbound")
    if direct_to_me:
        reasons.append("direct to you")
    elif cc_to_me:
        reasons.append("cc to you")
    if question and not last_sender_is_me:
        reasons.append("explicit question")
    if urgent:
        reasons.append("urgent wording")
    if finance:
        reasons.append("finance-related")
    if scheduling:
        reasons.append("scheduling-related")
    if automated:
        reasons.append("automated sender")
    if broadcast:
        reasons.append("broadcast-style message")
    if security_info:
        reasons.append("informational security notice")
    if passive_update:
        reasons.append("passive status update")
    if cold_outreach:
        reasons.append("cold outreach")
    if recruiter_outreach:
        reasons.append("recruiter outreach")
    if recruiting_process:
        reasons.append("recruiting process")
    if logistics_request:
        reasons.append("logistics request")
    if calendar_invite:
        reasons.append("calendar invite")
    if resolved_hint:
        reasons.append("closure language")
    if stale_days >= 2:
        reasons.append(f"stale {stale_days}d")
    if dormant_single_inbound:
        reasons.append("dormant one-off thread")
    if len(external_participants) > 1:
        reasons.append("multiple external participants")

    if not external_participants:
        followup_state = "ambiguous"
        reasons.append("internal-only thread")
    elif cold_outreach:
        followup_state = "ambiguous"
    elif recruiter_outreach and not prior_outbound:
        followup_state = "ambiguous"
    elif calendar_invite and not direct_request:
        followup_state = "ambiguous"
    elif (broadcast or security_info or automated) and not direct_request:
        followup_state = "ambiguous"
    elif dormant_single_inbound:
        followup_state = "ambiguous"
    elif passive_update and not direct_request:
        followup_state = "waiting_on_them"
    elif resolved_hint and not unread_inbound_count:
        followup_state = "resolved"
    elif len(ordered) == 1 and last_sender_is_me:
        followup_state = "ambiguous"
        reasons.append("single outbound message")
    elif last_sender_is_me:
        followup_state = "waiting_on_them"
    elif stale_days > 120 and unread_inbound_count == 0 and not direct_request:
        followup_state = "ambiguous"
    else:
        followup_state = "waiting_on_me"

    score = _base_score_for(followup_state)
    if unread_inbound_count:
        score += min(0.18, unread_inbound_count * 0.08)
    if direct_to_me:
        score += 0.12
    elif cc_to_me:
        score += 0.05
    if question and not last_sender_is_me:
        score += 0.10
    if urgent:
        score += 0.12
    if finance:
        score += 0.10
    if scheduling:
        score += 0.08
    if stale_days >= 2:
        score += min(0.15, 0.03 * min(stale_days, 5))
    if len(external_participants) > 1:
        score += 0.04
    if automated:
        score -= 0.20
    if broadcast:
        score -= 0.25
    if security_info:
        score -= 0.15
    if passive_update:
        score -= 0.18
    if cold_outreach:
        score -= 0.25
    if recruiter_outreach:
        score -= 0.18
    if recruiting_process:
        score -= 0.10
    if logistics_request:
        score -= 0.10
    if calendar_invite:
        score -= 0.18
    if resolved_hint:
        score -= 0.20
    if not external_participants:
        score -= 0.10
    if dormant_single_inbound:
        score -= 0.12
    if stale_days > 45:
        score -= min(0.35, (stale_days - 45) * 0.002)
    if stale_days > 90 and unread_inbound_count == 0:
        score -= min(0.20, (stale_days - 90) * 0.0015)

    if followup_state == "resolved":
        score = min(score, 0.20)
    elif followup_state == "ambiguous":
        score = min(score, 0.45)

    return ThreadTriageAssessment(
        last_message_at=last_message.event_at.isoformat() if last_message.event_at != datetime.min.replace(tzinfo=timezone.utc) else None,
        unread_count=unread_inbound_count,
        importance_score=max(0.0, min(0.99, round(score, 2))),
        followup_state=followup_state,
        participants=all_participants,
        classification_tags=_deduplicate(reasons),
    )


def refresh_thread_triage(
    config: AppConfig,
    *,
    account_id: str = "all",
    thread_ids: Sequence[str] | None = None,
) -> int:
    """Recompute thread-level triage metadata from normalized messages."""

    initialize_database(config)
    with connect_db(config.db_path) as connection:
        rows = _load_thread_message_rows(connection, account_id=account_id, thread_ids=thread_ids)
        if not rows:
            return 0
        aliases_by_account = _load_account_aliases(connection, account_ids={str(row["account_id"]) for row in rows})
        grouped: dict[str, dict[str, object]] = {}
        for row in rows:
            thread_id = str(row["thread_id"])
            grouped.setdefault(
                thread_id,
                {
                    "account_id": str(row["account_id"]),
                    "messages": [],
                },
            )
            grouped[thread_id]["messages"].append(
                ThreadMessageSnapshot(
                    sender=str(row["sender"]),
                    to_recipients=_json_list(row["to_recipients"]),
                    cc_recipients=_json_list(row["cc_recipients"]),
                    bcc_recipients=_json_list(row["bcc_recipients"]),
                    sent_at=_parse_datetime(row["sent_at"]),
                    received_at=_parse_datetime(row["received_at"]),
                    snippet=str(row["snippet"]),
                    body_text=str(row["body_text"]),
                    flags=_json_list(row["flags"]),
                )
            )

        for thread_id, payload in grouped.items():
            resolved_account_id = str(payload["account_id"])
            assessment = assess_thread(
                subject=str(rows_by_thread_subject(rows, thread_id)),
                account_aliases=aliases_by_account.get(resolved_account_id, {resolved_account_id}),
                messages=list(payload["messages"]),
            )
            connection.execute(
                """
                UPDATE threads
                SET
                    participants = ?,
                    last_message_at = ?,
                    unread_count = ?,
                    importance_score = ?,
                    followup_state = ?,
                    classification_tags = ?
                WHERE id = ?
                """,
                (
                    json.dumps(assessment.participants, ensure_ascii=True, sort_keys=True),
                    assessment.last_message_at,
                    assessment.unread_count,
                    assessment.importance_score,
                    assessment.followup_state,
                    json.dumps(assessment.classification_tags, ensure_ascii=True, sort_keys=True),
                    thread_id,
                ),
            )
        return len(grouped)


def list_triage_threads(
    config: AppConfig,
    *,
    older_than_days: int,
    account_id: str,
    states: Sequence[str] | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    """Return ranked triage rows from local thread state."""

    initialize_database(config)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
    sql = """
        SELECT
            id,
            account_id,
            subject,
            last_message_at,
            unread_count,
            importance_score,
            followup_state,
            classification_tags
        FROM threads
        WHERE last_message_at IS NOT NULL
          AND last_message_at <= ?
    """
    parameters: list[object] = [cutoff]
    if account_id != "all":
        sql += " AND account_id = ?"
        parameters.append(account_id)
    if states:
        placeholders = ", ".join("?" for _ in states)
        sql += f" AND followup_state IN ({placeholders})"
        parameters.extend(states)
    sql += " ORDER BY importance_score DESC, last_message_at ASC LIMIT ?"
    parameters.append(limit)

    with connect_db(config.db_path) as connection:
        rows = connection.execute(sql, tuple(parameters)).fetchall()

    return [
        {
            "id": str(row["id"]),
            "account_id": str(row["account_id"]),
            "subject": str(row["subject"]),
            "last_message_at": str(row["last_message_at"]),
            "unread_count": int(row["unread_count"]),
            "importance_score": float(row["importance_score"]),
            "followup_state": str(row["followup_state"]),
            "classification_tags": _json_list(row["classification_tags"]),
        }
        for row in rows
    ]


def summarize_followup_states(config: AppConfig, *, account_id: str) -> dict[str, int]:
    """Return thread counts by follow-up state."""

    initialize_database(config)
    sql = "SELECT followup_state, COUNT(*) AS count FROM threads"
    parameters: list[object] = []
    if account_id != "all":
        sql += " WHERE account_id = ?"
        parameters.append(account_id)
    sql += " GROUP BY followup_state"

    summary = {
        "waiting_on_me": 0,
        "waiting_on_them": 0,
        "resolved": 0,
        "ambiguous": 0,
    }
    with connect_db(config.db_path) as connection:
        rows = connection.execute(sql, tuple(parameters)).fetchall()
    for row in rows:
        summary[str(row["followup_state"])] = int(row["count"])
    return summary


def _load_thread_message_rows(
    connection: sqlite3.Connection,
    *,
    account_id: str,
    thread_ids: Sequence[str] | None,
) -> list[sqlite3.Row]:
    sql = """
        SELECT
            threads.id AS thread_id,
            threads.account_id AS account_id,
            threads.subject AS subject,
            messages.sender AS sender,
            messages.to_recipients AS to_recipients,
            messages.cc_recipients AS cc_recipients,
            messages.bcc_recipients AS bcc_recipients,
            messages.sent_at AS sent_at,
            messages.received_at AS received_at,
            messages.snippet AS snippet,
            messages.body_text AS body_text,
            messages.flags AS flags
        FROM threads
        JOIN messages ON messages.thread_id = threads.id
    """
    parameters: list[object] = []
    clauses: list[str] = []
    if account_id != "all":
        clauses.append("threads.account_id = ?")
        parameters.append(account_id)
    if thread_ids:
        placeholders = ", ".join("?" for _ in thread_ids)
        clauses.append(f"threads.id IN ({placeholders})")
        parameters.extend(thread_ids)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY threads.id ASC, COALESCE(messages.received_at, messages.sent_at, '') ASC"
    return connection.execute(sql, tuple(parameters)).fetchall()


def _load_account_aliases(connection: sqlite3.Connection, *, account_ids: Iterable[str]) -> dict[str, set[str]]:
    identifiers = sorted({item for item in account_ids if item})
    aliases: dict[str, set[str]] = {account_id: {account_id} for account_id in identifiers}
    if not identifiers:
        return aliases

    placeholders = ", ".join("?" for _ in identifiers)
    account_rows = connection.execute(
        f"SELECT id, email_address FROM accounts WHERE id IN ({placeholders})",
        tuple(identifiers),
    ).fetchall()
    for row in account_rows:
        aliases[str(row["id"])].add(str(row["email_address"]).strip().lower())

    alias_rows = connection.execute(
        f"SELECT account_id, alias_email FROM account_aliases WHERE account_id IN ({placeholders})",
        tuple(identifiers),
    ).fetchall()
    for row in alias_rows:
        aliases.setdefault(str(row["account_id"]), {str(row["account_id"])})
        aliases[str(row["account_id"])].add(str(row["alias_email"]).strip().lower())
    return aliases


def _base_score_for(followup_state: str) -> float:
    if followup_state == "waiting_on_me":
        return 0.55
    if followup_state == "waiting_on_them":
        return 0.32
    if followup_state == "resolved":
        return 0.05
    return 0.15


def _contains_any(value: str, needles: Sequence[str]) -> bool:
    return any(needle in value for needle in needles)


def _deduplicate(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _has_seen_flag(flags: Sequence[str]) -> bool:
    return any(flag.lower() == "\\seen" for flag in flags)


def _json_list(raw_value: object) -> list[str]:
    if raw_value in (None, ""):
        return []
    if isinstance(raw_value, list):
        return [str(item).strip().lower() for item in raw_value if str(item).strip()]
    return [str(item).strip().lower() for item in json.loads(str(raw_value)) if str(item).strip()]


def _looks_automated_sender(sender: str) -> bool:
    local_part = sender.split("@", 1)[0].strip().lower()
    return any(local_part.startswith(prefix) for prefix in AUTOMATED_LOCAL_PARTS)


def _sender_domain(sender: str) -> str:
    if "@" not in sender:
        return ""
    return sender.split("@", 1)[1].strip().lower()


def _normalized_text(*values: str) -> str:
    return " ".join(value.strip().lower() for value in values if value and value.strip())


def _parse_datetime(raw_value: object) -> datetime | None:
    if raw_value in (None, ""):
        return None
    parsed = datetime.fromisoformat(str(raw_value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def rows_by_thread_subject(rows: Sequence[sqlite3.Row], thread_id: str) -> str:
    for row in rows:
        if str(row["thread_id"]) == thread_id:
            return str(row["subject"])
    return ""


def _extract_recent_body(body_text: str) -> str:
    lowered = body_text.lower()
    cutoffs = [
        lowered.find(marker)
        for marker in QUOTE_MARKERS
        if lowered.find(marker) != -1
    ]
    for pattern in QUOTE_PATTERNS:
        match = pattern.search(body_text)
        if match is not None:
            cutoffs.append(match.start())
    if cutoffs:
        return body_text[: min(cutoffs)].strip()
    return body_text.strip()
