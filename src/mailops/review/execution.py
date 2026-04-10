"""Provider-backed execution for approved review batches."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Callable

from pydantic import BaseModel, Field

from mailops.adapters.proton_bridge.adapter import ProtonBridgeAdapter
from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.adapters.proton_bridge.drafts import DraftCreateRequest
from mailops.core.config import AppConfig
from mailops.core.exceptions import AdapterError
from mailops.core.models import ExecutionStatus
from mailops.index.db import (
    connect_db,
    create_audit_event,
    initialize_database,
    new_identifier,
    update_action_proposal_execution,
    update_review_batch_status,
)
from mailops.review.batches import approve_review_batch, get_review_batch
from mailops.review.proton_profiles import resolve_proton_overrides


class BatchExecutionResult(BaseModel):
    batch_id: str
    batch_status: str
    executed_actions: int = 0
    pending_actions: int = 0
    failed_actions: int = 0
    errors: list[str] = Field(default_factory=list)


def execute_review_batch(
    config: AppConfig,
    batch_id: str,
    *,
    actor: str = "operator",
    proton_overrides: BridgeDiscoveryOverrides | None = None,
    proton_adapter_factory: Callable[[AppConfig], ProtonBridgeAdapter] | None = None,
) -> BatchExecutionResult | None:
    """Approve a batch and materialize any executable provider-side draft actions."""

    initialize_database(config)
    approved = approve_review_batch(config, batch_id, actor=actor)
    if approved is None:
        return None
    if approved.highest_risk.value == "high":
        return BatchExecutionResult(batch_id=batch_id, batch_status=approved.status, pending_actions=len(approved.actions))
    if approved.status == "rolled_back":
        return BatchExecutionResult(batch_id=batch_id, batch_status=approved.status, pending_actions=len(approved.actions))

    executable_actions = [action for action in approved.actions if action.type == "create_draft" and action.draft_proposal_id]
    if not executable_actions:
        return BatchExecutionResult(batch_id=batch_id, batch_status=approved.status)

    executed_actions = 0
    failed_actions = 0
    errors: list[str] = []
    with connect_db(config.db_path) as connection:
        for action in executable_actions:
            if action.execution_status not in {ExecutionStatus.PENDING, ExecutionStatus.FAILED}:
                continue
            target_row = connection.execute(
                """
                SELECT
                    action_proposals.id AS action_id,
                    action_proposals.draft_proposal_id AS draft_proposal_id,
                    draft_proposals.account_id AS draft_account_id,
                    draft_proposals.to_recipients AS draft_to_recipients,
                    draft_proposals.cc_recipients AS draft_cc_recipients,
                    draft_proposals.bcc_recipients AS draft_bcc_recipients,
                    draft_proposals.in_reply_to AS draft_in_reply_to,
                    draft_proposals.reference_message_ids AS draft_reference_message_ids,
                    draft_proposals.proposed_subject AS proposed_subject,
                    draft_proposals.proposed_body AS proposed_body,
                    threads.id AS thread_id,
                    COALESCE(NULLIF(draft_proposals.account_id, ''), threads.account_id) AS account_id,
                    accounts.provider AS provider,
                    accounts.email_address AS account_email,
                    accounts.adapter_config_ref AS adapter_config_ref,
                    messages.sender AS latest_sender,
                    messages.provider_message_id AS latest_provider_message_id
                FROM action_proposals
                JOIN draft_proposals
                  ON draft_proposals.id = action_proposals.draft_proposal_id
                LEFT JOIN threads
                  ON threads.id = draft_proposals.thread_id
                JOIN accounts
                  ON accounts.id = COALESCE(NULLIF(draft_proposals.account_id, ''), threads.account_id)
                LEFT JOIN messages
                  ON messages.id = (
                      SELECT candidate.id
                      FROM messages AS candidate
                      WHERE candidate.thread_id = threads.id
                      ORDER BY COALESCE(candidate.received_at, candidate.sent_at, '') DESC
                      LIMIT 1
                  )
                WHERE action_proposals.id = ?
                """,
                (action.id,),
            ).fetchone()
            if target_row is None:
                failed_actions += 1
                error_message = f"Action '{action.id}' is missing its draft execution context."
                errors.append(error_message)
                update_action_proposal_execution(
                    connection,
                    proposal_id=action.id,
                    execution_status=ExecutionStatus.FAILED.value,
                )
                create_audit_event(
                    connection,
                    event_id=new_identifier("audit"),
                    actor=actor,
                    action_type="draft_materialization_failed",
                    target_ref=action.id,
                    timestamp=_utc_now(),
                    result="failed",
                    before_state={"execution_status": action.execution_status.value},
                    after_state={"execution_status": ExecutionStatus.FAILED.value, "error": error_message},
                )
                continue

            try:
                provider = str(target_row["provider"])
                if provider != "proton_bridge":
                    raise AdapterError(f"Provider '{provider}' does not yet support draft materialization.")

                account_id = str(target_row["account_id"])
                account_email = str(target_row["account_email"])
                to_recipients = _json_list(target_row["draft_to_recipients"])
                cc_recipients = _json_list(target_row["draft_cc_recipients"])
                bcc_recipients = _json_list(target_row["draft_bcc_recipients"])
                in_reply_to = _canonical_message_id(target_row["draft_in_reply_to"])
                reference_message_ids = [
                    message_id
                    for message_id in (_canonical_message_id(item) for item in _json_list(target_row["draft_reference_message_ids"]))
                    if message_id
                ]
                if not to_recipients:
                    latest_sender = str(target_row["latest_sender"] or "").strip().lower()
                    if not latest_sender or latest_sender == account_email:
                        raise AdapterError(f"Thread '{target_row['thread_id']}' has no external recipient to draft against.")
                    to_recipients = [latest_sender]
                    in_reply_to = in_reply_to or _canonical_message_id(target_row["latest_provider_message_id"])
                    if not reference_message_ids and in_reply_to:
                        reference_message_ids = [in_reply_to]

                adapter = (
                    proton_adapter_factory(config)
                    if proton_adapter_factory is not None
                    else ProtonBridgeAdapter(config)
                )
                resolved_overrides = resolve_proton_overrides(
                    config,
                    account_id=account_id,
                    account_email=account_email,
                    adapter_config_ref=str(target_row["adapter_config_ref"]) if target_row["adapter_config_ref"] else None,
                    explicit=proton_overrides,
                )
                endpoint = adapter.discover(overrides=resolved_overrides)
                if not endpoint.is_usable():
                    errors.append(
                        f"Action '{action.id}': Proton Bridge credentials are not currently available for account '{account_id}'."
                    )
                    continue
                result = adapter.create_draft(
                    DraftCreateRequest(
                        account_id=account_id,
                        from_address=account_email,
                        to_recipients=to_recipients,
                        cc_recipients=cc_recipients,
                        bcc_recipients=bcc_recipients,
                        subject=str(target_row["proposed_subject"]),
                        body_text=str(target_row["proposed_body"]),
                        in_reply_to=in_reply_to,
                        references=reference_message_ids,
                    ),
                    overrides=resolved_overrides,
                )
                update_action_proposal_execution(
                    connection,
                    proposal_id=action.id,
                    execution_status=ExecutionStatus.EXECUTED.value,
                    provider_ref=result.provider_ref,
                )
                create_audit_event(
                    connection,
                    event_id=new_identifier("audit"),
                    actor=actor,
                    action_type="draft_materialized",
                    target_ref=action.id,
                    timestamp=_utc_now(),
                    result="executed",
                    before_state={"execution_status": action.execution_status.value},
                    after_state={
                        "execution_status": ExecutionStatus.EXECUTED.value,
                        "provider_ref": result.provider_ref,
                        "mailbox": result.mailbox,
                    },
                )
                executed_actions += 1
            except AdapterError as exc:
                failed_actions += 1
                error_message = str(exc)
                errors.append(f"Action '{action.id}': {error_message}")
                update_action_proposal_execution(
                    connection,
                    proposal_id=action.id,
                    execution_status=ExecutionStatus.FAILED.value,
                )
                create_audit_event(
                    connection,
                    event_id=new_identifier("audit"),
                    actor=actor,
                    action_type="draft_materialization_failed",
                    target_ref=action.id,
                    timestamp=_utc_now(),
                    result="failed",
                    before_state={"execution_status": action.execution_status.value},
                    after_state={"execution_status": ExecutionStatus.FAILED.value, "error": error_message},
                )

        refreshed_actions = connection.execute(
            """
            SELECT execution_status
            FROM action_proposals
            WHERE batch_id = ?
            """,
            (batch_id,),
        ).fetchall()
        refreshed_batch = connection.execute(
            "SELECT status FROM review_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        if refreshed_batch is not None:
            pending_actions = sum(
                1 for row in refreshed_actions if str(row["execution_status"]) == ExecutionStatus.PENDING.value
            )
            failed_count = sum(
                1 for row in refreshed_actions if str(row["execution_status"]) == ExecutionStatus.FAILED.value
            )
            executed_count = sum(
                1 for row in refreshed_actions if str(row["execution_status"]) == ExecutionStatus.EXECUTED.value
            )
            current_status = str(refreshed_batch["status"])
            next_status = current_status
            if executed_count and pending_actions == 0 and failed_count == 0:
                next_status = "executed"
            elif executed_count and (pending_actions > 0 or failed_count > 0):
                next_status = "partially_executed"
            update_review_batch_status(connection, batch_id=batch_id, status=next_status)
            if next_status != current_status:
                create_audit_event(
                    connection,
                    event_id=new_identifier("audit"),
                    actor=actor,
                    action_type="review_batch_executed",
                    target_ref=batch_id,
                    timestamp=_utc_now(),
                    result=next_status,
                    before_state={"status": current_status},
                    after_state={"status": next_status},
                )

    final_batch = get_review_batch(config, batch_id)
    if final_batch is None:
        return None
    return BatchExecutionResult(
        batch_id=batch_id,
        batch_status=final_batch.status,
        executed_actions=executed_actions,
        pending_actions=sum(1 for action in final_batch.actions if action.execution_status == ExecutionStatus.PENDING),
        failed_actions=sum(1 for action in final_batch.actions if action.execution_status == ExecutionStatus.FAILED),
        errors=errors,
    )


def _canonical_message_id(raw_value: object) -> str | None:
    if raw_value in (None, ""):
        return None
    value = str(raw_value).strip()
    if value.startswith("<") and value.endswith(">"):
        return value
    return None


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
