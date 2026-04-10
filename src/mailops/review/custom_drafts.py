"""Review-first custom draft proposal creation."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from mailops.core.config import AppConfig
from mailops.core.models import ProviderName
from mailops.index.db import (
    connect_db,
    create_action_proposal,
    create_audit_event,
    create_draft_proposal,
    create_review_batch,
    initialize_database,
    new_identifier,
)


class CustomDraftRequest(BaseModel):
    to_recipients: list[str]
    subject: str
    body_text: str
    account_id: str | None = None
    provider: ProviderName = ProviderName.PROTON_BRIDGE
    cc_recipients: list[str] = Field(default_factory=list)
    bcc_recipients: list[str] = Field(default_factory=list)
    context_refs: list[str] = Field(default_factory=list)
    rationale: str = "Operator-created custom draft proposal."


class CustomDraftBatchResult(BaseModel):
    batch_id: str
    draft_id: str
    account_id: str
    to_recipients: list[str]
    subject: str


def create_custom_draft_review_batch(config: AppConfig, request: CustomDraftRequest) -> CustomDraftBatchResult:
    """Create a pending review batch for an explicit outbound draft."""

    initialize_database(config)
    to_recipients = _clean_addresses(request.to_recipients)
    cc_recipients = _clean_addresses(request.cc_recipients)
    bcc_recipients = _clean_addresses(request.bcc_recipients)
    if not to_recipients:
        raise ValueError("at least one --to recipient is required")
    if not request.subject.strip():
        raise ValueError("--subject is required")
    if not request.body_text.strip():
        raise ValueError("draft body is required")

    with connect_db(config.db_path) as connection:
        account = _resolve_account(
            connection,
            provider=request.provider.value,
            account_id=request.account_id,
        )
        created_at = datetime.now(timezone.utc).isoformat()
        batch_id = new_identifier("batch")
        draft_id = new_identifier("draft")
        action_id = new_identifier("action")
        thread_ref = f"custom_draft:{draft_id}"
        scope = [
            f"account:{account['id']}",
            *[f"to:{recipient}" for recipient in to_recipients],
            *request.context_refs,
        ]

        create_review_batch(
            connection,
            batch_id=batch_id,
            batch_type="custom_draft",
            status="pending",
            scope_count=1,
            highest_risk="medium",
            reason="Custom outbound draft proposal created for operator review.",
            rollback_available=True,
            created_at=created_at,
        )
        create_draft_proposal(
            connection,
            proposal_id=draft_id,
            thread_id=thread_ref,
            account_id=str(account["id"]),
            to_recipients=to_recipients,
            cc_recipients=cc_recipients,
            bcc_recipients=bcc_recipients,
            context_refs=request.context_refs,
            style_profile="custom",
            proposed_subject=request.subject.strip(),
            proposed_body=request.body_text.strip(),
            confidence=1.0,
            rationale=request.rationale,
            created_at=created_at,
        )
        create_action_proposal(
            connection,
            proposal_id=action_id,
            batch_id=batch_id,
            action_type="create_draft",
            scope=scope,
            reason="Materialize this custom outbound message as a provider draft after review.",
            evidence_refs=request.context_refs,
            draft_proposal_id=draft_id,
            risk_level="medium",
            review_status="pending",
            execution_status="pending",
            created_at=created_at,
        )
        create_audit_event(
            connection,
            event_id=new_identifier("audit"),
            actor="mailops.draft",
            action_type="custom_draft_batch_created",
            target_ref=batch_id,
            timestamp=created_at,
            result="pending_review",
            after_state={
                "draft_id": draft_id,
                "account_id": str(account["id"]),
                "to_recipients": to_recipients,
                "context_refs": request.context_refs,
            },
        )

    return CustomDraftBatchResult(
        batch_id=batch_id,
        draft_id=draft_id,
        account_id=str(account["id"]),
        to_recipients=to_recipients,
        subject=request.subject.strip(),
    )


def _resolve_account(connection: object, *, provider: str, account_id: str | None) -> dict[str, object]:
    if account_id:
        row = connection.execute(
            """
            SELECT id, email_address
            FROM accounts
            WHERE provider = ?
              AND (id = ? OR email_address = ?)
            """,
            (provider, account_id.strip().lower(), account_id.strip().lower()),
        ).fetchone()
        if row is None:
            raise ValueError(f"account '{account_id}' was not found for provider '{provider}'")
        return {"id": str(row["id"]), "email_address": str(row["email_address"])}

    rows = connection.execute(
        """
        SELECT id, email_address
        FROM accounts
        WHERE provider = ?
        ORDER BY id ASC
        """,
        (provider,),
    ).fetchall()
    if not rows:
        raise ValueError(f"no local accounts found for provider '{provider}'")
    if len(rows) > 1:
        choices = ", ".join(str(row["id"]) for row in rows)
        raise ValueError(f"multiple '{provider}' accounts are available; pass --from-account. Choices: {choices}")
    row = rows[0]
    return {"id": str(row["id"]), "email_address": str(row["email_address"])}


def _clean_addresses(values: list[str]) -> list[str]:
    return [value.strip().lower() for value in values if value.strip()]
