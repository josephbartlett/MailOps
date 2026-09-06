"""Provider draft reconciliation for executed review actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from pydantic import BaseModel, Field

from mailops.adapters.proton_bridge.adapter import ProtonBridgeAdapter
from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.core.config import AppConfig
from mailops.core.exceptions import AdapterError
from mailops.index.db import (
    connect_db,
    create_audit_event,
    initialize_database,
    new_identifier,
    upsert_provider_draft_snapshot,
)
from mailops.review.batches import get_review_batch
from mailops.review.proton_profiles import resolve_proton_overrides


class ProviderDraftSyncResult(BaseModel):
    batch_id: str
    synced_drafts: int = 0
    missing_drafts: int = 0
    failed_drafts: int = 0
    errors: list[str] = Field(default_factory=list)


def sync_review_batch_provider_drafts(
    config: AppConfig,
    batch_id: str,
    *,
    actor: str = "operator",
    proton_overrides: BridgeDiscoveryOverrides | None = None,
    proton_adapter_factory: Callable[[AppConfig], ProtonBridgeAdapter] | None = None,
) -> ProviderDraftSyncResult | None:
    """Look up executed provider draft refs and persist local metadata snapshots."""

    initialize_database(config)
    batch = get_review_batch(config, batch_id)
    if batch is None:
        return None

    targets = _load_provider_draft_targets(config, batch_id)
    result = ProviderDraftSyncResult(batch_id=batch_id)
    for target in targets:
        provider = str(target["provider"])
        action_id = str(target["action_id"])
        provider_ref = str(target["provider_ref"])
        if provider != "proton_bridge":
            result.failed_drafts += 1
            error = f"Action '{action_id}': provider '{provider}' does not support draft lookup yet."
            result.errors.append(error)
            _record_lookup_failure(config, actor=actor, action_id=action_id, error=error)
            continue

        try:
            account_id = str(target["account_id"])
            account_email = str(target["account_email"])
            adapter = (
                proton_adapter_factory(config)
                if proton_adapter_factory is not None
                else ProtonBridgeAdapter(config)
            )
            resolved_overrides = resolve_proton_overrides(
                config,
                account_id=account_id,
                account_email=account_email,
                adapter_config_ref=str(target["adapter_config_ref"]) if target["adapter_config_ref"] else None,
                explicit=proton_overrides,
            )
            lookup = adapter.lookup_draft(
                account_id=account_id,
                provider_ref=provider_ref,
                overrides=resolved_overrides,
            )
            synced_at = _utc_now()
            with connect_db(config.db_path) as connection:
                upsert_provider_draft_snapshot(
                    connection,
                    action_id=action_id,
                    batch_id=batch_id,
                    draft_proposal_id=str(target["draft_proposal_id"]) if target["draft_proposal_id"] else None,
                    account_id=account_id,
                    provider=provider,
                    provider_ref=provider_ref,
                    mailbox=lookup.mailbox,
                    uid=lookup.uid,
                    provider_message_id=lookup.provider_message_id,
                    subject=lookup.subject,
                    from_address=lookup.from_address,
                    to_recipients=lookup.to_recipients,
                    cc_recipients=lookup.cc_recipients,
                    bcc_recipients=lookup.bcc_recipients,
                    flags=lookup.flags,
                    internal_date=lookup.internal_date.isoformat() if lookup.internal_date else None,
                    synced_at=synced_at,
                    status=lookup.status,
                )
                create_audit_event(
                    connection,
                    event_id=new_identifier("audit"),
                    actor=actor,
                    action_type="provider_draft_synced",
                    target_ref=action_id,
                    timestamp=synced_at,
                    result=lookup.status,
                    after_state={
                        "provider_ref": provider_ref,
                        "mailbox": lookup.mailbox,
                        "uid": lookup.uid,
                        "provider_message_id": lookup.provider_message_id,
                        "status": lookup.status,
                    },
                )
            if lookup.status == "present":
                result.synced_drafts += 1
            elif lookup.status == "missing":
                result.missing_drafts += 1
            else:
                result.failed_drafts += 1
                result.errors.append(f"Action '{action_id}': draft lookup returned status '{lookup.status}'.")
        except AdapterError as exc:
            result.failed_drafts += 1
            error = f"Action '{action_id}': {exc}"
            result.errors.append(error)
            _record_lookup_failure(config, actor=actor, action_id=action_id, error=error)

    return result


def _load_provider_draft_targets(config: AppConfig, batch_id: str) -> list[object]:
    with connect_db(config.db_path) as connection:
        return connection.execute(
            """
            SELECT
                action_proposals.id AS action_id,
                action_proposals.draft_proposal_id AS draft_proposal_id,
                action_proposals.provider_ref AS provider_ref,
                COALESCE(NULLIF(draft_proposals.account_id, ''), threads.account_id) AS account_id,
                accounts.provider AS provider,
                accounts.email_address AS account_email,
                accounts.adapter_config_ref AS adapter_config_ref
            FROM action_proposals
            JOIN draft_proposals
              ON draft_proposals.id = action_proposals.draft_proposal_id
            LEFT JOIN threads
              ON threads.id = draft_proposals.thread_id
            JOIN accounts
              ON accounts.id = COALESCE(NULLIF(draft_proposals.account_id, ''), threads.account_id)
            WHERE action_proposals.batch_id = ?
              AND action_proposals.type = 'create_draft'
              AND action_proposals.execution_status = 'executed'
              AND action_proposals.provider_ref IS NOT NULL
            ORDER BY action_proposals.created_at ASC, action_proposals.id ASC
            """,
            (batch_id,),
        ).fetchall()


def _record_lookup_failure(config: AppConfig, *, actor: str, action_id: str, error: str) -> None:
    with connect_db(config.db_path) as connection:
        create_audit_event(
            connection,
            event_id=new_identifier("audit"),
            actor=actor,
            action_type="provider_draft_sync_failed",
            target_ref=action_id,
            timestamp=_utc_now(),
            result="failed",
            after_state={"error": error},
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
