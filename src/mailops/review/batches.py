"""Review batch persistence and local lifecycle helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from mailops.core.config import AppConfig
from mailops.core.models import (
    ActionProposal,
    AuditEvent,
    DraftProposal,
    ExecutionStatus,
    ProviderDraftSnapshot,
    ProviderName,
    ReviewBatchDetail,
    ReviewBatchSummary,
    ReviewStatus,
    RiskTier,
)
from mailops.index.db import (
    connect_db,
    create_audit_event,
    delete_draft_proposals,
    initialize_database,
    new_identifier,
    update_batch_action_statuses,
    update_review_batch_status,
)


def list_review_batches(config: AppConfig) -> list[ReviewBatchSummary]:
    """Return locally persisted review batches."""

    initialize_database(config)
    with connect_db(config.db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, type, status, scope_count, highest_risk, reason, rollback_available, created_at
            FROM review_batches
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [_row_to_review_batch_summary(row) for row in rows]


def get_review_batch(config: AppConfig, batch_id: str) -> ReviewBatchDetail | None:
    """Return a single review batch and its local artifacts."""

    initialize_database(config)
    with connect_db(config.db_path) as connection:
        batch_row = connection.execute(
            """
            SELECT id, type, status, scope_count, highest_risk, reason, rollback_available, created_at
            FROM review_batches
            WHERE id = ?
            """,
            (batch_id,),
        ).fetchone()
        if batch_row is None:
            return None

        action_rows = connection.execute(
            """
            SELECT
                id,
                batch_id,
                type,
                scope,
                reason,
                evidence_refs,
                draft_proposal_id,
                provider_ref,
                risk_level,
                review_status,
                execution_status,
                created_at
            FROM action_proposals
            WHERE batch_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (batch_id,),
        ).fetchall()
        draft_ids = [str(row["draft_proposal_id"]) for row in action_rows if row["draft_proposal_id"]]
        draft_rows = []
        if draft_ids:
            placeholders = ", ".join("?" for _ in draft_ids)
            draft_rows = connection.execute(
                f"""
                SELECT
                    id,
                    thread_id,
                    account_id,
                    to_recipients,
                    cc_recipients,
                    bcc_recipients,
                    in_reply_to,
                    reference_message_ids,
                    context_refs,
                    style_profile,
                    proposed_subject,
                    proposed_body,
                    confidence,
                    rationale,
                    created_at
                FROM draft_proposals
                WHERE id IN ({placeholders})
                ORDER BY created_at ASC, id ASC
                """,
                tuple(draft_ids),
            ).fetchall()
        provider_draft_rows = connection.execute(
            """
            SELECT
                action_id,
                batch_id,
                draft_proposal_id,
                account_id,
                provider,
                provider_ref,
                mailbox,
                uid,
                provider_message_id,
                subject,
                from_address,
                to_recipients,
                cc_recipients,
                bcc_recipients,
                flags,
                internal_date,
                synced_at,
                status
            FROM provider_drafts
            WHERE batch_id = ?
            ORDER BY synced_at ASC, action_id ASC
            """,
            (batch_id,),
        ).fetchall()

    summary = _row_to_review_batch_summary(batch_row)
    return ReviewBatchDetail(
        **summary.model_dump(),
        actions=[_row_to_action_proposal(row) for row in action_rows],
        draft_proposals=[_row_to_draft_proposal(row) for row in draft_rows],
        provider_drafts=[_row_to_provider_draft_snapshot(row) for row in provider_draft_rows],
    )


def approve_review_batch(config: AppConfig, batch_id: str, *, actor: str = "operator") -> ReviewBatchDetail | None:
    """Approve a pending batch without faking provider-side execution."""

    initialize_database(config)
    batch = get_review_batch(config, batch_id)
    if batch is None:
        return None
    if batch.highest_risk == RiskTier.HIGH:
        _record_batch_audit(
            config,
            batch_id=batch_id,
            actor=actor,
            action_type="review_batch_blocked",
            before_state={"status": batch.status},
            after_state={"status": batch.status},
            result="blocked",
        )
        return batch
    if batch.status in {"approved", "executed", "partially_executed"}:
        return batch
    if batch.status == "rolled_back":
        return batch

    with connect_db(config.db_path) as connection:
        update_review_batch_status(connection, batch_id=batch_id, status="approved")
        update_batch_action_statuses(
            connection,
            batch_id=batch_id,
            review_status=ReviewStatus.APPROVED.value,
            execution_status=ExecutionStatus.PENDING.value,
        )
        create_audit_event(
            connection,
            event_id=new_identifier("audit"),
            actor=actor,
            action_type="review_batch_approved",
            target_ref=batch_id,
            timestamp=_utc_now(),
            result="approved",
            before_state={"status": batch.status},
            after_state={"status": "approved"},
        )

    return get_review_batch(config, batch_id)


def rollback_review_batch(config: AppConfig, batch_id: str, *, actor: str = "operator") -> ReviewBatchDetail | None:
    """Rollback local draft artifacts for a review batch."""

    initialize_database(config)
    batch = get_review_batch(config, batch_id)
    if batch is None:
        return None
    if batch.status == "rolled_back":
        return batch
    if any(action.execution_status == ExecutionStatus.EXECUTED for action in batch.actions):
        _record_batch_audit(
            config,
            batch_id=batch_id,
            actor=actor,
            action_type="review_batch_rollback_blocked",
            before_state={"status": batch.status},
            after_state={"status": batch.status},
            result="provider_drafts_present",
        )
        return batch

    proposal_ids = [draft.id for draft in batch.draft_proposals]
    with connect_db(config.db_path) as connection:
        delete_draft_proposals(connection, proposal_ids=proposal_ids)
        update_batch_action_statuses(
            connection,
            batch_id=batch_id,
            review_status=ReviewStatus.REJECTED.value,
            execution_status=ExecutionStatus.ROLLED_BACK.value,
        )
        update_review_batch_status(connection, batch_id=batch_id, status="rolled_back")
        create_audit_event(
            connection,
            event_id=new_identifier("audit"),
            actor=actor,
            action_type="review_batch_rolled_back",
            target_ref=batch_id,
            timestamp=_utc_now(),
            result="rolled_back",
            before_state={"status": batch.status, "draft_proposal_ids": proposal_ids},
            after_state={"status": "rolled_back", "deleted_draft_proposal_ids": proposal_ids},
        )

    return get_review_batch(config, batch_id)


def list_audit_events(config: AppConfig, *, limit: int = 25) -> list[AuditEvent]:
    """Return recent audit events."""

    initialize_database(config)
    with connect_db(config.db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, actor, action_type, target_ref, timestamp, before_state, after_state, result
            FROM audit_events
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_audit_event(row) for row in rows]


def _record_batch_audit(
    config: AppConfig,
    *,
    batch_id: str,
    actor: str,
    action_type: str,
    before_state: dict[str, object],
    after_state: dict[str, object],
    result: str,
) -> None:
    initialize_database(config)
    with connect_db(config.db_path) as connection:
        create_audit_event(
            connection,
            event_id=new_identifier("audit"),
            actor=actor,
            action_type=action_type,
            target_ref=batch_id,
            timestamp=_utc_now(),
            result=result,
            before_state=before_state,
            after_state=after_state,
        )


def _row_to_review_batch_summary(row: object) -> ReviewBatchSummary:
    return ReviewBatchSummary(
        batch_id=str(row["id"]),
        batch_type=str(row["type"]),
        status=str(row["status"]),
        scope_count=int(row["scope_count"]),
        highest_risk=RiskTier(str(row["highest_risk"])),
        reason=str(row["reason"]),
        rollback_available=bool(int(row["rollback_available"])),
        created_at=_parse_datetime(str(row["created_at"])),
    )


def _row_to_action_proposal(row: object) -> ActionProposal:
    return ActionProposal(
        id=str(row["id"]),
        batch_id=str(row["batch_id"]),
        type=str(row["type"]),
        scope=_json_list(row["scope"]),
        reason=str(row["reason"]),
        evidence_refs=_json_list(row["evidence_refs"]),
        draft_proposal_id=str(row["draft_proposal_id"]) if row["draft_proposal_id"] else None,
        provider_ref=str(row["provider_ref"]) if row["provider_ref"] else None,
        risk_level=RiskTier(str(row["risk_level"])),
        review_status=ReviewStatus(str(row["review_status"])),
        execution_status=ExecutionStatus(str(row["execution_status"])),
        created_at=_parse_datetime(str(row["created_at"])),
    )


def _row_to_draft_proposal(row: object) -> DraftProposal:
    return DraftProposal(
        id=str(row["id"]),
        thread_id=str(row["thread_id"]),
        account_id=str(row["account_id"]) if row["account_id"] else None,
        to_recipients=_json_list(row["to_recipients"]),
        cc_recipients=_json_list(row["cc_recipients"]),
        bcc_recipients=_json_list(row["bcc_recipients"]),
        in_reply_to=str(row["in_reply_to"]) if row["in_reply_to"] else None,
        reference_message_ids=_json_list(row["reference_message_ids"]),
        context_refs=_json_list(row["context_refs"]),
        style_profile=str(row["style_profile"]),
        proposed_subject=str(row["proposed_subject"]),
        proposed_body=str(row["proposed_body"]),
        confidence=float(row["confidence"]),
        rationale=str(row["rationale"]),
        created_at=_parse_datetime(str(row["created_at"])),
    )


def _row_to_provider_draft_snapshot(row: object) -> ProviderDraftSnapshot:
    return ProviderDraftSnapshot(
        action_id=str(row["action_id"]),
        batch_id=str(row["batch_id"]),
        draft_proposal_id=str(row["draft_proposal_id"]) if row["draft_proposal_id"] else None,
        account_id=str(row["account_id"]),
        provider=ProviderName(str(row["provider"])),
        provider_ref=str(row["provider_ref"]),
        mailbox=str(row["mailbox"]),
        uid=int(row["uid"]) if row["uid"] is not None else None,
        provider_message_id=str(row["provider_message_id"]) if row["provider_message_id"] else None,
        subject=str(row["subject"]),
        from_address=str(row["from_address"]),
        to_recipients=_json_list(row["to_recipients"]),
        cc_recipients=_json_list(row["cc_recipients"]),
        bcc_recipients=_json_list(row["bcc_recipients"]),
        flags=_json_list(row["flags"]),
        internal_date=_parse_optional_datetime(row["internal_date"]),
        synced_at=_parse_datetime(str(row["synced_at"])),
        status=str(row["status"]),
    )


def _row_to_audit_event(row: object) -> AuditEvent:
    return AuditEvent(
        id=str(row["id"]),
        actor=str(row["actor"]),
        action_type=str(row["action_type"]),
        target_ref=str(row["target_ref"]),
        timestamp=_parse_datetime(str(row["timestamp"])),
        before_state=_json_dict(row["before_state"]),
        after_state=_json_dict(row["after_state"]),
        result=str(row["result"]),
    )


def _json_list(raw_value: object) -> list[str]:
    if raw_value in (None, ""):
        return []
    return [str(item) for item in json.loads(str(raw_value))]


def _json_dict(raw_value: object) -> dict[str, object] | None:
    if raw_value in (None, ""):
        return None
    return dict(json.loads(str(raw_value)))


def _parse_datetime(raw_value: str) -> datetime:
    parsed = datetime.fromisoformat(raw_value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_optional_datetime(raw_value: object) -> datetime | None:
    if raw_value in (None, ""):
        return None
    return _parse_datetime(str(raw_value))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
