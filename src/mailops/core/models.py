"""Domain models used by MailOps."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class MailOpsModel(BaseModel):
    """Base model configuration for domain objects."""

    model_config = ConfigDict(use_enum_values=False)


class ProviderName(str, Enum):
    PROTON_BRIDGE = "proton_bridge"
    GMAIL_API = "gmail_api"
    DEMO_LOCAL = "demo_local"


class SyncStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class FollowupState(str, Enum):
    WAITING_ON_ME = "waiting_on_me"
    WAITING_ON_THEM = "waiting_on_them"
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    BLOCKED = "blocked"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Account(MailOpsModel):
    id: str
    provider: ProviderName
    display_name: str
    email_address: str
    adapter_config_ref: str | None = None
    last_sync_at: datetime | None = None
    sync_status: SyncStatus = SyncStatus.PENDING


class AccountAlias(MailOpsModel):
    alias_email: str
    account_id: str
    provider_username: str | None = None
    is_primary: bool = False


class Thread(MailOpsModel):
    id: str
    provider_thread_id: str
    account_id: str
    subject: str
    participants: list[str] = Field(default_factory=list)
    last_message_at: datetime | None = None
    unread_count: int = 0
    importance_score: float = 0.0
    followup_state: FollowupState = FollowupState.AMBIGUOUS
    classification_tags: list[str] = Field(default_factory=list)


class Folder(MailOpsModel):
    id: str
    account_id: str
    provider_folder_id: str
    display_name: str
    delimiter: str = "/"
    attributes: list[str] = Field(default_factory=list)
    role: str = "unknown"
    is_selectable: bool = True
    can_sync: bool = True
    can_create_draft: bool = False
    last_uid: int = 0
    last_sync_at: datetime | None = None


class Message(MailOpsModel):
    id: str
    provider_message_id: str
    thread_id: str
    sender: str
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    sent_at: datetime | None = None
    received_at: datetime | None = None
    snippet: str = ""
    body_text: str = ""
    folder_or_label_refs: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class DraftProposal(MailOpsModel):
    id: str
    thread_id: str
    account_id: str | None = None
    to_recipients: list[str] = Field(default_factory=list)
    cc_recipients: list[str] = Field(default_factory=list)
    bcc_recipients: list[str] = Field(default_factory=list)
    in_reply_to: str | None = None
    reference_message_ids: list[str] = Field(default_factory=list)
    context_refs: list[str] = Field(default_factory=list)
    style_profile: str = "default"
    proposed_subject: str
    proposed_body: str
    confidence: float = 0.0
    rationale: str
    created_at: datetime = Field(default_factory=utc_now)


class ActionProposal(MailOpsModel):
    id: str
    batch_id: str
    type: str
    scope: list[str] = Field(default_factory=list)
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    draft_proposal_id: str | None = None
    provider_ref: str | None = None
    risk_level: RiskTier = RiskTier.LOW
    review_status: ReviewStatus = ReviewStatus.PENDING
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)


class ProviderDraftSnapshot(MailOpsModel):
    action_id: str
    batch_id: str
    draft_proposal_id: str | None = None
    account_id: str
    provider: ProviderName
    provider_ref: str
    mailbox: str
    uid: int | None = None
    provider_message_id: str | None = None
    subject: str = ""
    from_address: str = ""
    to_recipients: list[str] = Field(default_factory=list)
    cc_recipients: list[str] = Field(default_factory=list)
    bcc_recipients: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    internal_date: datetime | None = None
    synced_at: datetime = Field(default_factory=utc_now)
    status: str = "unknown"


class RuleProposal(MailOpsModel):
    id: str
    provider: ProviderName
    natural_language_intent: str
    structured_conditions: dict[str, Any] = Field(default_factory=dict)
    generated_rule_text: str
    explanation: str
    test_preview: str | None = None


class AuditEvent(MailOpsModel):
    id: str
    actor: str
    action_type: str
    target_ref: str
    timestamp: datetime = Field(default_factory=utc_now)
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    result: str = "pending"


class ReviewBatchSummary(MailOpsModel):
    batch_id: str
    batch_type: str
    status: str
    scope_count: int
    highest_risk: RiskTier
    reason: str
    rollback_available: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class ReviewBatchDetail(ReviewBatchSummary):
    actions: list[ActionProposal] = Field(default_factory=list)
    draft_proposals: list[DraftProposal] = Field(default_factory=list)
    provider_drafts: list[ProviderDraftSnapshot] = Field(default_factory=list)


class SyncResult(MailOpsModel):
    account_id: str
    provider: str
    folders_synced: list[str] = Field(default_factory=list)
    folders_discovered: list[str] = Field(default_factory=list)
    messages_indexed: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
