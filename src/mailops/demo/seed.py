"""Seed a small local mailbox dataset for contributor testing."""

from __future__ import annotations

from dataclasses import dataclass

from mailops.core.config import AppConfig
from mailops.index.db import (
    connect_db,
    initialize_database,
    link_message_to_folder,
    upsert_account,
    upsert_account_alias,
    upsert_folder,
    upsert_message,
    upsert_thread,
)
from mailops.index.triage import refresh_thread_triage


@dataclass(frozen=True)
class DemoSeedResult:
    account_id: str
    threads: int
    messages: int


DEMO_ACCOUNT_ID = "demo@example.com"
DEMO_PROVIDER = "demo_local"


def seed_demo_mailbox(config: AppConfig) -> DemoSeedResult:
    """Upsert a deterministic local-only mailbox fixture."""

    initialize_database(config)
    with connect_db(config.db_path) as connection:
        upsert_account(
            connection,
            account_id=DEMO_ACCOUNT_ID,
            provider=DEMO_PROVIDER,
            display_name="MailOps Demo",
            email_address=DEMO_ACCOUNT_ID,
            sync_status="ready",
        )
        upsert_account_alias(
            connection,
            alias_email=DEMO_ACCOUNT_ID,
            account_id=DEMO_ACCOUNT_ID,
            provider_username=DEMO_ACCOUNT_ID,
            is_primary=True,
        )
        upsert_folder(
            connection,
            folder_id="demo:inbox",
            account_id=DEMO_ACCOUNT_ID,
            provider_folder_id="INBOX",
            display_name="INBOX",
            delimiter="/",
            attributes=[],
            role="inbox",
            is_selectable=True,
            can_sync=True,
            can_create_draft=False,
            last_uid=5,
            last_sync_at="2026-04-10T12:00:00+00:00",
        )
        upsert_folder(
            connection,
            folder_id="demo:sent",
            account_id=DEMO_ACCOUNT_ID,
            provider_folder_id="Sent",
            display_name="Sent",
            delimiter="/",
            attributes=[r"\Sent"],
            role="sent",
            is_selectable=True,
            can_sync=True,
            can_create_draft=False,
            last_uid=1,
            last_sync_at="2026-04-10T12:00:00+00:00",
        )

        for item in _demo_messages():
            upsert_thread(
                connection,
                thread_id=item["thread_id"],
                account_id=DEMO_ACCOUNT_ID,
                provider_thread_id=item["thread_id"],
                subject=item["subject"],
                participants=item["participants"],
                last_message_at=item["received_at"],
                unread_count=0,
                importance_score=0.0,
                followup_state="ambiguous",
                classification_tags=[],
            )
            upsert_message(
                connection,
                message_id=item["message_id"],
                provider_message_id=item["provider_message_id"],
                thread_id=item["thread_id"],
                sender=item["sender"],
                to_recipients=item["to"],
                cc_recipients=[],
                bcc_recipients=[],
                sent_at=item["sent_at"],
                received_at=item["received_at"],
                snippet=item["snippet"],
                body_text=item["body"],
                folder_or_label_refs=[item["folder"]],
                flags=item["flags"],
            )
            link_message_to_folder(
                connection,
                folder_id="demo:sent" if item["folder"] == "Sent" else "demo:inbox",
                provider_message_id=item["provider_message_id"],
                uid=item["uid"],
                flags=item["flags"],
            )

    refresh_thread_triage(config, account_id=DEMO_ACCOUNT_ID)
    return DemoSeedResult(account_id=DEMO_ACCOUNT_ID, threads=5, messages=6)


def _demo_messages() -> list[dict[str, object]]:
    return [
        {
            "thread_id": "demo-thread-scheduling",
            "message_id": "demo-message-scheduling",
            "provider_message_id": "<demo-scheduling@example.com>",
            "subject": "Scheduling implementation review",
            "participants": ["client@example.com", DEMO_ACCOUNT_ID],
            "sender": "client@example.com",
            "to": [DEMO_ACCOUNT_ID],
            "sent_at": "2026-04-09T14:00:00+00:00",
            "received_at": "2026-04-09T14:00:00+00:00",
            "snippet": "Can you send availability for a review meeting?",
            "body": "Can you send availability for a review meeting this week?",
            "folder": "INBOX",
            "flags": [],
            "uid": 1,
        },
        {
            "thread_id": "demo-thread-finance",
            "message_id": "demo-message-finance",
            "provider_message_id": "<demo-finance@example.com>",
            "subject": "Invoice approval needed",
            "participants": ["vendor@example.com", DEMO_ACCOUNT_ID],
            "sender": "vendor@example.com",
            "to": [DEMO_ACCOUNT_ID],
            "sent_at": "2026-04-09T16:00:00+00:00",
            "received_at": "2026-04-09T16:00:00+00:00",
            "snippet": "Please confirm whether invoice 1042 is approved for payment.",
            "body": "Please confirm whether invoice 1042 is approved for payment.",
            "folder": "INBOX",
            "flags": [],
            "uid": 2,
        },
        {
            "thread_id": "demo-thread-waiting",
            "message_id": "demo-message-waiting-inbound",
            "provider_message_id": "<demo-waiting-inbound@example.com>",
            "subject": "Contract language",
            "participants": ["legal@example.com", DEMO_ACCOUNT_ID],
            "sender": "legal@example.com",
            "to": [DEMO_ACCOUNT_ID],
            "sent_at": "2026-04-08T17:00:00+00:00",
            "received_at": "2026-04-08T17:00:00+00:00",
            "snippet": "Can you review the updated clause?",
            "body": "Can you review the updated clause and send comments?",
            "folder": "INBOX",
            "flags": [r"\Seen"],
            "uid": 5,
        },
        {
            "thread_id": "demo-thread-waiting",
            "message_id": "demo-message-waiting",
            "provider_message_id": "<demo-waiting@example.com>",
            "subject": "Re: Contract language",
            "participants": ["legal@example.com", DEMO_ACCOUNT_ID],
            "sender": DEMO_ACCOUNT_ID,
            "to": ["legal@example.com"],
            "sent_at": "2026-04-08T18:00:00+00:00",
            "received_at": "2026-04-08T18:00:00+00:00",
            "snippet": "I reviewed the clause and sent comments.",
            "body": "I reviewed the clause and sent comments. Waiting on your confirmation.",
            "folder": "Sent",
            "flags": [r"\Seen"],
            "uid": 1,
        },
        {
            "thread_id": "demo-thread-newsletter",
            "message_id": "demo-message-newsletter",
            "provider_message_id": "<demo-newsletter@example.com>",
            "subject": "Weekly product newsletter",
            "participants": ["newsletter@example.com", DEMO_ACCOUNT_ID],
            "sender": "newsletter@example.com",
            "to": [DEMO_ACCOUNT_ID],
            "sent_at": "2026-04-07T12:00:00+00:00",
            "received_at": "2026-04-07T12:00:00+00:00",
            "snippet": "News, resources, and events for this week.",
            "body": "News, resources, and events for this week.",
            "folder": "INBOX",
            "flags": [r"\Seen"],
            "uid": 3,
        },
        {
            "thread_id": "demo-thread-resolved",
            "message_id": "demo-message-resolved",
            "provider_message_id": "<demo-resolved@example.com>",
            "subject": "Re: Access request",
            "participants": ["teammate@example.com", DEMO_ACCOUNT_ID],
            "sender": "teammate@example.com",
            "to": [DEMO_ACCOUNT_ID],
            "sent_at": "2026-04-06T15:00:00+00:00",
            "received_at": "2026-04-06T15:00:00+00:00",
            "snippet": "Thanks, all set.",
            "body": "Thanks, all set.",
            "folder": "INBOX",
            "flags": [r"\Seen"],
            "uid": 4,
        },
    ]
