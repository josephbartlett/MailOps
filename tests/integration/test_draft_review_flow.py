from __future__ import annotations

from email import message_from_bytes

from pydantic import SecretStr
from typer.testing import CliRunner

from mailops.adapters.proton_bridge.adapter import ProtonBridgeAdapter
from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.cli.main import app
from mailops.core.config import AppConfig
from mailops.index.db import (
    connect_db,
    get_table_counts,
    get_pending_action_proposal_count,
    initialize_database,
    upsert_account,
    upsert_account_alias,
    upsert_message,
    upsert_thread,
)
from mailops.index.triage import refresh_thread_triage
from mailops.review.batches import get_review_batch, list_review_batches
from mailops.review.custom_drafts import CustomDraftRequest, create_custom_draft_review_batch
from mailops.review.execution import execute_review_batch
from mailops.review.provider_drafts import sync_review_batch_provider_drafts


runner = CliRunner()


def _seed_waiting_on_me_thread(config: AppConfig) -> str:
    initialize_database(config)
    thread_id = "thread_sched_001"
    with connect_db(config.db_path) as connection:
        upsert_account(
            connection,
            account_id="ops@example.com",
            provider="proton_bridge",
            display_name="ops@example.com",
            email_address="ops@example.com",
            sync_status="ready",
        )
        upsert_account_alias(
            connection,
            alias_email="ops@example.com",
            account_id="ops@example.com",
            provider_username="ops@example.com",
            is_primary=True,
        )
        upsert_thread(
            connection,
            thread_id=thread_id,
            account_id="ops@example.com",
            provider_thread_id="provider-thread-001",
            subject="Scheduling next steps",
            participants=["client@example.com", "ops@example.com"],
            last_message_at="2026-04-08T10:00:00+00:00",
            unread_count=1,
            importance_score=0.0,
            followup_state="waiting_on_me",
            classification_tags=[],
        )
        upsert_message(
            connection,
            message_id="message_sched_001",
            provider_message_id="<sched-001@example.com>",
            thread_id=thread_id,
            sender="client@example.com",
            to_recipients=["ops@example.com"],
            cc_recipients=[],
            bcc_recipients=[],
            sent_at="2026-04-08T10:00:00+00:00",
            received_at="2026-04-08T10:00:00+00:00",
            snippet="Can you share availability for a meeting this week?",
            body_text="Can you share availability for a meeting this week?",
            folder_or_label_refs=["INBOX"],
            flags=[],
        )
    refresh_thread_triage(config)
    return thread_id


def test_local_draft_review_flow(tmp_path, monkeypatch) -> None:
    home = tmp_path / ".mailops"
    monkeypatch.setenv("MAILOPS_HOME", str(home))
    config = AppConfig(home_dir=home)
    _seed_waiting_on_me_thread(config)
    runner = CliRunner()

    ask_result = runner.invoke(app, ["ask", "draft replies for scheduling emails from this week"])
    assert ask_result.exit_code == 0, ask_result.output
    assert "Created review batch" in ask_result.output

    batches = list_review_batches(config)
    assert len(batches) == 1
    batch_id = batches[0].batch_id

    review_result = runner.invoke(app, ["review", "batch", "show", batch_id])
    assert review_result.exit_code == 0, review_result.output
    assert "Draft Proposals" in review_result.output
    assert "Scheduling next steps" in review_result.output

    apply_result = runner.invoke(app, ["apply", batch_id])
    assert apply_result.exit_code == 0, apply_result.output
    assert "Approved batch" in apply_result.output

    approved_batch = get_review_batch(config, batch_id)
    assert approved_batch is not None
    assert approved_batch.status == "approved"
    assert approved_batch.actions[0].review_status.value == "approved"

    export_result = runner.invoke(app, ["export", "audit"])
    assert export_result.exit_code == 0, export_result.output
    assert batch_id in export_result.output
    assert "review_batch_approved" in export_result.output

    rollback_result = runner.invoke(app, ["rollback", batch_id])
    assert rollback_result.exit_code == 0, rollback_result.output
    assert "Rolled back local artifacts" in rollback_result.output

    rolled_back_batch = get_review_batch(config, batch_id)
    assert rolled_back_batch is not None
    assert rolled_back_batch.status == "rolled_back"
    assert rolled_back_batch.draft_proposals == []

    counts = get_table_counts(config)
    assert counts["draft_proposals"] == 0
    assert counts["action_proposals"] == 1
    assert counts["review_batches"] == 1
    assert counts["audit_events"] == 3


class FakeDraftExecutionImapClient:
    def __init__(self) -> None:
        self.appended_messages: list[bytes] = []

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        return "OK", [b"logged in"]

    def list(self) -> tuple[str, list[bytes]]:
        return "OK", [b'(\\HasNoChildren \\Drafts) "/" "Drafts"', b'(\\HasNoChildren) "/" "INBOX"']

    def append(self, mailbox: str, flags: str, date_time: object, raw_message: bytes) -> tuple[str, list[bytes]]:
        assert mailbox == "Drafts"
        assert flags == r"(\Draft)"
        self.appended_messages.append(raw_message)
        return "OK", [b"[APPENDUID 7 99] APPEND completed"]

    def select(self, mailbox: str, readonly: bool = False) -> tuple[str, list[bytes]]:
        assert mailbox == "Drafts"
        assert readonly is True
        return "OK", [b"1"]

    def uid(self, command: str, *args: object) -> tuple[str, list[object]]:
        assert command == "FETCH"
        assert args[0] == "99"
        if not self.appended_messages:
            return "OK", []
        return (
            "OK",
            [
                (
                    b'99 (UID 99 FLAGS (\\Draft) INTERNALDATE "10-Apr-2026 01:26:04 +0000" BODY[HEADER.FIELDS (MESSAGE-ID FROM TO CC BCC SUBJECT DATE)] {1}',
                    self.appended_messages[0],
                )
            ],
        )

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b"logged out"]


def test_execute_review_batch_materializes_provider_draft(tmp_path, monkeypatch) -> None:
    home = tmp_path / ".mailops"
    monkeypatch.setenv("MAILOPS_HOME", str(home))
    config = AppConfig(home_dir=home)
    _seed_waiting_on_me_thread(config)
    runner = CliRunner()

    ask_result = runner.invoke(app, ["ask", "draft replies for scheduling emails from this week"])
    assert ask_result.exit_code == 0, ask_result.output

    batch_id = list_review_batches(config)[0].batch_id
    client = FakeDraftExecutionImapClient()
    result = execute_review_batch(
        config,
        batch_id,
        actor="test.apply",
        proton_overrides=BridgeDiscoveryOverrides(
            username="bridge-user",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
        ),
        proton_adapter_factory=lambda cfg: ProtonBridgeAdapter(cfg, imap_client_factory=lambda endpoint: client),
    )

    assert result is not None
    assert result.executed_actions == 1
    assert result.failed_actions == 0
    assert result.pending_actions == 0
    assert len(client.appended_messages) == 1

    parsed = message_from_bytes(client.appended_messages[0])
    assert parsed["To"] == "client@example.com"
    assert parsed["From"] == "ops@example.com"
    assert parsed["Subject"] == "Re: Scheduling next steps"

    executed_batch = get_review_batch(config, batch_id)
    assert executed_batch is not None
    assert executed_batch.status == "executed"
    assert executed_batch.actions[0].execution_status.value == "executed"
    assert executed_batch.actions[0].provider_ref == "Drafts:uid:99"
    assert get_pending_action_proposal_count(config) == 0

    sync_result = sync_review_batch_provider_drafts(
        config,
        batch_id,
        actor="test.sync_drafts",
        proton_overrides=BridgeDiscoveryOverrides(
            username="bridge-user",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
        ),
        proton_adapter_factory=lambda cfg: ProtonBridgeAdapter(cfg, imap_client_factory=lambda endpoint: client),
    )

    assert sync_result is not None
    assert sync_result.synced_drafts == 1
    synced_batch = get_review_batch(config, batch_id)
    assert synced_batch is not None
    assert len(synced_batch.provider_drafts) == 1
    assert synced_batch.provider_drafts[0].status == "present"
    assert synced_batch.provider_drafts[0].uid == 99
    assert synced_batch.provider_drafts[0].subject == "Re: Scheduling next steps"


def test_custom_draft_review_batch_materializes_provider_draft(tmp_path, monkeypatch) -> None:
    home = tmp_path / ".mailops"
    monkeypatch.setenv("MAILOPS_HOME", str(home))
    config = AppConfig(home_dir=home)
    initialize_database(config)
    with connect_db(config.db_path) as connection:
        upsert_account(
            connection,
            account_id="ops@example.com",
            provider="proton_bridge",
            display_name="ops@example.com",
            email_address="ops@example.com",
            sync_status="ready",
        )
        upsert_account_alias(
            connection,
            alias_email="ops@example.com",
            account_id="ops@example.com",
            provider_username="ops@example.com",
            is_primary=True,
        )

    created = create_custom_draft_review_batch(
        config,
        CustomDraftRequest(
            account_id="ops@example.com",
            to_recipients=["client@example.com"],
            cc_recipients=["lead@example.com"],
            subject="Project update",
            body_text="We finished the local validation and the next step is release review.",
            context_refs=["repo:MailOps", "test:70-passed"],
        ),
    )

    batch = get_review_batch(config, created.batch_id)
    assert batch is not None
    assert batch.batch_type == "custom_draft"
    assert batch.status == "pending"
    assert batch.draft_proposals[0].thread_id.startswith("custom_draft:")
    assert batch.draft_proposals[0].account_id == "ops@example.com"
    assert batch.draft_proposals[0].to_recipients == ["client@example.com"]
    assert batch.draft_proposals[0].cc_recipients == ["lead@example.com"]
    assert batch.draft_proposals[0].context_refs == ["repo:MailOps", "test:70-passed"]

    client = FakeDraftExecutionImapClient()
    result = execute_review_batch(
        config,
        created.batch_id,
        actor="test.apply",
        proton_overrides=BridgeDiscoveryOverrides(
            username="bridge-user",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
        ),
        proton_adapter_factory=lambda cfg: ProtonBridgeAdapter(cfg, imap_client_factory=lambda endpoint: client),
    )

    assert result is not None
    assert result.executed_actions == 1
    assert result.failed_actions == 0
    assert result.pending_actions == 0

    parsed = message_from_bytes(client.appended_messages[0])
    assert parsed["To"] == "client@example.com"
    assert parsed["Cc"] == "lead@example.com"
    assert parsed["From"] == "ops@example.com"
    assert parsed["Subject"] == "Project update"
    assert parsed["In-Reply-To"] is None
    assert "release review" in parsed.get_payload()

    sync_result = sync_review_batch_provider_drafts(
        config,
        created.batch_id,
        actor="test.sync_drafts",
        proton_overrides=BridgeDiscoveryOverrides(
            username="bridge-user",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
        ),
        proton_adapter_factory=lambda cfg: ProtonBridgeAdapter(cfg, imap_client_factory=lambda endpoint: client),
    )

    assert sync_result is not None
    assert sync_result.synced_drafts == 1
    synced_batch = get_review_batch(config, created.batch_id)
    assert synced_batch is not None
    assert synced_batch.provider_drafts[0].subject == "Project update"
    assert synced_batch.provider_drafts[0].to_recipients == ["client@example.com"]


def test_review_batch_show_renders_full_custom_draft_envelope(tmp_path, monkeypatch) -> None:
    home = tmp_path / ".mailops"
    monkeypatch.setenv("MAILOPS_HOME", str(home))
    config = AppConfig(home_dir=home)
    initialize_database(config)
    with connect_db(config.db_path) as connection:
        upsert_account(
            connection,
            account_id="ops@example.com",
            provider="proton_bridge",
            display_name="ops@example.com",
            email_address="ops@example.com",
            sync_status="ready",
        )
        upsert_account_alias(
            connection,
            alias_email="ops@example.com",
            account_id="ops@example.com",
            provider_username="ops@example.com",
            is_primary=True,
        )

    created = create_custom_draft_review_batch(
        config,
        CustomDraftRequest(
            account_id="ops@example.com",
            to_recipients=["client@example.com"],
            cc_recipients=["lead@example.com"],
            bcc_recipients=["hidden@example.com"],
            subject="Project update",
            body_text="Review-first draft body.",
            context_refs=["repo:MailOps"],
        ),
    )

    batch = get_review_batch(config, created.batch_id)
    assert batch is not None
    assert "cc:lead@example.com" in batch.actions[0].scope
    assert "bcc:hidden@example.com" in batch.actions[0].scope

    result = runner.invoke(app, ["review", "batch", "show", created.batch_id])

    assert result.exit_code == 0, result.output
    assert "client@example.com" in result.output
    assert "lead@example.com" in result.output
    assert "hidden@example.com" in result.output
