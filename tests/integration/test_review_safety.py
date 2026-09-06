from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.adapters.proton_bridge.drafts import DraftCreateResult
from mailops.adapters.proton_bridge.registry import ProtonAccountProfile, save_profile
from mailops.agent.drafts import create_draft_review_batch
from mailops.core.config import AppConfig
from mailops.core.exceptions import AdapterError
from mailops.index.db import connect_db, initialize_database, upsert_account, upsert_account_alias, upsert_message, upsert_thread
from mailops.review.batches import approve_review_batch, get_review_batch, list_audit_events, rollback_review_batch
from mailops.review.custom_drafts import CustomDraftRequest, create_custom_draft_review_batch
from mailops.review.execution import execute_review_batch
from mailops.review import execution


@pytest.fixture
def config(tmp_path):
    config = AppConfig(home_dir=tmp_path / "mailops")
    initialize_database(config)
    with connect_db(config.db_path) as connection:
        upsert_account(connection, account_id="ops@example.com", provider="proton_bridge",
                       display_name="Operator", email_address="ops@example.com", sync_status="ready")
    return config


def make_batch(config):
    return create_custom_draft_review_batch(config, CustomDraftRequest(
        account_id="ops@example.com", to_recipients=["client@example.com"],
        subject="Review me", body_text="A reviewed draft.",
    )).batch_id


class RecordingAdapter:
    def __init__(self):
        self.requests = []

    def discover(self, *, overrides):
        return SimpleNamespace(is_usable=lambda: True)

    def create_draft(self, request, *, overrides):
        self.requests.append(request)
        return DraftCreateResult(account_id=request.account_id, mailbox="Drafts",
                                 provider_ref="Drafts:uid:99", message_id="<draft@example.com>")


def apply(config, batch_id, adapter, **kwargs):
    return execute_review_batch(config, batch_id, proton_adapter_factory=lambda _: adapter, **kwargs)


def test_apply_does_not_retry_provider_write_with_uncertain_receipt(config):
    batch_id = make_batch(config)

    class LostReceiptAdapter(RecordingAdapter):
        def create_draft(self, request, *, overrides):
            self.requests.append(request)
            raise AdapterError("private password and mailbox content should not enter audit")

    adapter = LostReceiptAdapter()
    result = apply(config, batch_id, adapter)
    assert result.uncertain_actions == 1
    assert result.batch_status == "attention_required"
    assert "private password" not in str(list_audit_events(config))
    repeated = apply(config, batch_id, adapter)
    assert repeated.uncertain_actions == 1
    assert len(adapter.requests) == 1
    assert rollback_review_batch(config, batch_id).status == "attention_required"
    assert get_review_batch(config, batch_id).draft_proposals
    assert not get_review_batch(config, batch_id).rollback_available


def test_process_interruption_leaves_durable_claim_and_blocks_retry(config):
    batch_id = make_batch(config)

    class InterruptedAdapter(RecordingAdapter):
        def create_draft(self, request, *, overrides):
            self.requests.append(request)
            raise KeyboardInterrupt()

    adapter = InterruptedAdapter()
    with pytest.raises(KeyboardInterrupt):
        apply(config, batch_id, adapter)
    assert get_review_batch(config, batch_id).actions[0].execution_status.value == "executing"
    assert apply(config, batch_id, adapter).uncertain_actions == 1
    assert len(adapter.requests) == 1
    assert rollback_review_batch(config, batch_id).draft_proposals


def test_receipt_audit_failure_preserves_claim_without_partial_commit(config, monkeypatch):
    batch_id = make_batch(config)
    original = execution.create_audit_event

    def fail_receipt_audit(connection, **kwargs):
        if kwargs["action_type"] == "draft_materialized":
            raise RuntimeError("simulated private database detail")
        return original(connection, **kwargs)

    monkeypatch.setattr(execution, "create_audit_event", fail_receipt_audit)
    adapter = RecordingAdapter()
    assert apply(config, batch_id, adapter).uncertain_actions == 1
    action = get_review_batch(config, batch_id).actions[0]
    assert action.provider_ref is None
    assert action.execution_status.value == "uncertain"
    apply(config, batch_id, adapter)
    assert len(adapter.requests) == 1
    assert "private database detail" not in str(list_audit_events(config))


def test_concurrent_apply_materializes_each_draft_only_once(config):
    batch_id = make_batch(config)
    approve_review_batch(config, batch_id)
    barrier = Barrier(2)
    lock = Lock()

    class ConcurrentAdapter(RecordingAdapter):
        def discover(self, *, overrides):
            barrier.wait(timeout=10)
            return super().discover(overrides=overrides)

        def create_draft(self, request, *, overrides):
            with lock:
                return super().create_draft(request, overrides=overrides)

    adapter = ConcurrentAdapter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(apply, config, batch_id, adapter) for _ in range(2)]
        for future in futures:
            future.result(timeout=20)
    assert len(adapter.requests) == 1
    assert get_review_batch(config, batch_id).status == "executed"


def test_rollback_between_preparation_and_claim_prevents_provider_write(config):
    batch_id = make_batch(config)

    class RollbackDuringPreparation(RecordingAdapter):
        def discover(self, *, overrides):
            assert rollback_review_batch(config, batch_id).status == "rolled_back"
            return super().discover(overrides=overrides)

    adapter = RollbackDuringPreparation()
    assert apply(config, batch_id, adapter).batch_status == "rolled_back"
    assert not adapter.requests
    assert get_review_batch(config, batch_id).actions[0].execution_status.value == "rolled_back"


def test_completed_action_receipt_survives_interruption_of_later_action(config):
    batch_id = make_batch(config)
    second_batch_id = make_batch(config)
    with connect_db(config.db_path) as connection:
        connection.execute("UPDATE action_proposals SET batch_id = ? WHERE batch_id = ?", (batch_id, second_batch_id))

    class InterruptSecondAdapter(RecordingAdapter):
        def create_draft(self, request, *, overrides):
            if self.requests:
                self.requests.append(request)
                raise KeyboardInterrupt()
            return super().create_draft(request, overrides=overrides)

    adapter = InterruptSecondAdapter()
    with pytest.raises(KeyboardInterrupt):
        apply(config, batch_id, adapter)
    actions = get_review_batch(config, batch_id).actions
    assert sorted(action.execution_status.value for action in actions) == ["executed", "executing"]
    assert next(action for action in actions if action.execution_status.value == "executed").provider_ref == "Drafts:uid:99"
    apply(config, batch_id, adapter)
    assert len(adapter.requests) == 2


def test_header_injection_is_rejected_before_provider_claim(config):
    batch_id = make_batch(config)
    with connect_db(config.db_path) as connection:
        connection.execute("UPDATE draft_proposals SET proposed_subject = ?", ("Subject\r\nBcc: private@example.com",))
    adapter = RecordingAdapter()
    result = apply(config, batch_id, adapter)
    assert result.failed_actions == 1
    assert result.uncertain_actions == 0
    assert not adapter.requests
    assert "private@example.com" not in str(list_audit_events(config))


def test_understated_risk_batch_cannot_approve_provider_mutations(config):
    batch_id = make_batch(config)
    with connect_db(config.db_path) as connection:
        connection.execute("UPDATE action_proposals SET type = 'send_message', risk_level = 'low'")
        connection.execute("UPDATE review_batches SET highest_risk = 'low'")
    adapter = RecordingAdapter()
    assert approve_review_batch(config, batch_id).status == "pending"
    assert apply(config, batch_id, adapter).batch_status == "pending"
    assert not adapter.requests


def test_rejected_action_is_never_executed(config):
    batch_id = make_batch(config)
    approve_review_batch(config, batch_id)
    with connect_db(config.db_path) as connection:
        connection.execute("UPDATE action_proposals SET review_status = 'rejected'")
    adapter = RecordingAdapter()
    apply(config, batch_id, adapter)
    assert not adapter.requests


def test_profile_cannot_redirect_reviewed_draft_to_other_account(config):
    batch_id = make_batch(config)
    adapter = RecordingAdapter()
    result = apply(config, batch_id, adapter, proton_overrides=BridgeDiscoveryOverrides(
        account_email="other-company@example.com",
    ))
    assert result.failed_actions == 1
    assert "does not match" in result.errors[0]
    assert not adapter.requests


@pytest.mark.parametrize("username", ["other-account@example.com", "other-bridge-user"])
def test_username_override_cannot_redirect_reviewed_draft_while_preserving_display_identity(config, username):
    batch_id = make_batch(config)
    with connect_db(config.db_path) as connection:
        upsert_account(connection, account_id="other-account@example.com", provider="proton_bridge",
                       display_name="Other account", email_address="other-account@example.com", sync_status="ready")
        upsert_account_alias(connection, alias_email="other-account@example.com", account_id="other-account@example.com",
                             provider_username="other-bridge-user", is_primary=True)

    class NoDiscoveryAdapter(RecordingAdapter):
        def discover(self, *, overrides):
            pytest.fail("A foreign username must be rejected before provider discovery or login")

    adapter = NoDiscoveryAdapter()
    result = apply(config, batch_id, adapter, proton_overrides=BridgeDiscoveryOverrides(
        username=username, password=SecretStr("private-test-password"),
    ))
    assert result.failed_actions == 1
    assert result.uncertain_actions == 0
    assert "login username does not match" in result.errors[0]
    assert not adapter.requests
    assert "private-test-password" not in str(list_audit_events(config))


def test_username_override_accepts_known_provider_username_for_reviewed_account(config):
    batch_id = make_batch(config)
    with connect_db(config.db_path) as connection:
        upsert_account_alias(connection, alias_email="alias@example.com", account_id="ops@example.com",
                             provider_username="known-bridge-user", is_primary=False)
    adapter = RecordingAdapter()
    result = apply(config, batch_id, adapter, proton_overrides=BridgeDiscoveryOverrides(username="known-bridge-user"))
    assert result.executed_actions == 1
    assert len(adapter.requests) == 1


def test_username_override_accepts_pinned_saved_profile_username(config):
    batch_id = make_batch(config)
    save_profile(config, ProtonAccountProfile(profile_name="reviewed-account", username="saved-bridge-user",
                                             account_email="ops@example.com", canonical_email="ops@example.com"))
    with connect_db(config.db_path) as connection:
        connection.execute("UPDATE accounts SET adapter_config_ref = 'reviewed-account' WHERE id = 'ops@example.com'")
    adapter = RecordingAdapter()
    result = apply(config, batch_id, adapter, proton_overrides=BridgeDiscoveryOverrides(username="saved-bridge-user"))
    assert result.executed_actions == 1
    assert len(adapter.requests) == 1


def test_legacy_unaddressed_proposal_is_not_resolved_against_latest_sender(config):
    batch_id = make_batch(config)
    with connect_db(config.db_path) as connection:
        connection.execute("UPDATE draft_proposals SET to_recipients = '[]'")
    adapter = RecordingAdapter()
    result = apply(config, batch_id, adapter)
    assert result.failed_actions == 1
    assert "Recreate" in result.errors[0]
    assert not adapter.requests


def test_generated_draft_freezes_recipient_and_reply_target_before_later_sync(config):
    def add_message(message_id, sender, when):
        with connect_db(config.db_path) as connection:
            upsert_message(connection, message_id=message_id, provider_message_id=f"<{message_id}@example.com>",
                           thread_id="thread", sender=sender, to_recipients=["ops@example.com"],
                           cc_recipients=[], bcc_recipients=[], sent_at=when, received_at=when,
                           snippet="Please reply", body_text="Please reply", folder_or_label_refs=["INBOX"], flags=[])

    when = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with connect_db(config.db_path) as connection:
        upsert_thread(connection, thread_id="thread", account_id="ops@example.com", provider_thread_id="thread",
                      subject="Scheduling", participants=["client@example.com", "ops@example.com"],
                      last_message_at=when, unread_count=1, importance_score=1, followup_state="waiting_on_me", classification_tags=[])
    add_message("original", "client@example.com", when)
    created = create_draft_review_batch(config, "draft replies")
    assert created.batch_id
    proposal = get_review_batch(config, created.batch_id).draft_proposals[0]
    assert proposal.to_recipients == ["client@example.com"]
    assert proposal.in_reply_to == "<original@example.com>"
    add_message("later", "outsider@example.com", datetime.now(timezone.utc).isoformat())
    adapter = RecordingAdapter()
    result = apply(config, created.batch_id, adapter)
    assert result.executed_actions == 1
    assert adapter.requests[0].to_recipients == ["client@example.com"]
    assert adapter.requests[0].in_reply_to == "<original@example.com>"
