"""Read-only inspection helpers for indexed mailbox state."""

from __future__ import annotations

import json
from typing import Any

from mailops.core.config import AppConfig
from mailops.index.db import connect_db, initialize_database


def get_thread_detail(config: AppConfig, thread_id: str) -> dict[str, Any] | None:
    """Return a thread and its indexed messages from local state."""

    initialize_database(config)
    with connect_db(config.db_path) as connection:
        thread_row = connection.execute(
            """
            SELECT
                id,
                account_id,
                provider_thread_id,
                subject,
                participants,
                last_message_at,
                unread_count,
                importance_score,
                followup_state,
                classification_tags
            FROM threads
            WHERE id = ?
            """,
            (thread_id,),
        ).fetchone()
        if thread_row is None:
            return None

        message_rows = connection.execute(
            """
            SELECT
                id,
                provider_message_id,
                sender,
                to_recipients,
                cc_recipients,
                bcc_recipients,
                sent_at,
                received_at,
                snippet,
                body_text,
                folder_or_label_refs,
                flags
            FROM messages
            WHERE thread_id = ?
            ORDER BY COALESCE(received_at, sent_at, ''), id
            """,
            (thread_id,),
        ).fetchall()

    return {
        "thread": _thread_dict(thread_row),
        "messages": [_message_dict(row) for row in message_rows],
    }


def get_message_detail(config: AppConfig, message_id: str) -> dict[str, Any] | None:
    """Return a single indexed message with its parent thread metadata."""

    initialize_database(config)
    with connect_db(config.db_path) as connection:
        row = connection.execute(
            """
            SELECT
                messages.id AS id,
                messages.thread_id AS thread_id,
                messages.provider_message_id AS provider_message_id,
                messages.sender AS sender,
                messages.to_recipients AS to_recipients,
                messages.cc_recipients AS cc_recipients,
                messages.bcc_recipients AS bcc_recipients,
                messages.sent_at AS sent_at,
                messages.received_at AS received_at,
                messages.snippet AS snippet,
                messages.body_text AS body_text,
                messages.folder_or_label_refs AS folder_or_label_refs,
                messages.flags AS flags,
                threads.account_id AS account_id,
                threads.subject AS subject,
                threads.followup_state AS followup_state,
                threads.classification_tags AS classification_tags
            FROM messages
            JOIN threads ON threads.id = messages.thread_id
            WHERE messages.id = ?
            """,
            (message_id,),
        ).fetchone()
        if row is None:
            return None

    message = _message_dict(row)
    message["thread_id"] = str(row["thread_id"])
    return {
        "thread": {
            "id": str(row["thread_id"]),
            "account_id": str(row["account_id"]),
            "subject": str(row["subject"]),
            "followup_state": str(row["followup_state"]),
            "classification_tags": _json_list(row["classification_tags"]),
        },
        "message": message,
    }


def _thread_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "account_id": str(row["account_id"]),
        "provider_thread_id": str(row["provider_thread_id"]),
        "subject": str(row["subject"]),
        "participants": _json_list(row["participants"]),
        "last_message_at": str(row["last_message_at"] or ""),
        "unread_count": int(row["unread_count"]),
        "importance_score": float(row["importance_score"]),
        "followup_state": str(row["followup_state"]),
        "classification_tags": _json_list(row["classification_tags"]),
    }


def _message_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "provider_message_id": str(row["provider_message_id"]),
        "sender": str(row["sender"]),
        "to_recipients": _json_list(row["to_recipients"]),
        "cc_recipients": _json_list(row["cc_recipients"]),
        "bcc_recipients": _json_list(row["bcc_recipients"]),
        "sent_at": str(row["sent_at"] or ""),
        "received_at": str(row["received_at"] or ""),
        "snippet": str(row["snippet"] or ""),
        "body_text": str(row["body_text"] or ""),
        "folder_or_label_refs": _json_list(row["folder_or_label_refs"]),
        "flags": _json_list(row["flags"]),
    }


def _json_list(raw_value: object) -> list[str]:
    if raw_value in (None, ""):
        return []
    try:
        value = json.loads(str(raw_value))
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
