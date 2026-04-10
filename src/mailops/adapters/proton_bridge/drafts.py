"""Draft materialization primitives for Proton Bridge."""

from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pydantic import BaseModel, Field
import re


class DraftCreateRequest(BaseModel):
    account_id: str
    from_address: str
    to_recipients: list[str] = Field(default_factory=list)
    cc_recipients: list[str] = Field(default_factory=list)
    bcc_recipients: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)


class DraftCreateResult(BaseModel):
    account_id: str
    mailbox: str
    provider_ref: str
    message_id: str


class DraftLookupResult(BaseModel):
    account_id: str
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
    status: str = "unknown"


_APPENDUID_RE = re.compile(r"APPENDUID\s+\d+\s+(?P<uid>\d+)", re.IGNORECASE)
_UID_REF_MARKER = ":uid:"
_MESSAGE_ID_REF_MARKER = ":message-id:"


def build_draft_message(request: DraftCreateRequest) -> tuple[str, bytes]:
    """Build an RFC 822 draft payload for IMAP APPEND."""

    message = EmailMessage()
    message["From"] = request.from_address
    if request.to_recipients:
        message["To"] = ", ".join(request.to_recipients)
    if request.cc_recipients:
        message["Cc"] = ", ".join(request.cc_recipients)
    if request.bcc_recipients:
        message["Bcc"] = ", ".join(request.bcc_recipients)
    message["Subject"] = request.subject
    message["Date"] = format_datetime(requested_at())
    message_id = make_msgid(domain=_message_id_domain(request.from_address))
    message["Message-ID"] = message_id
    if request.in_reply_to:
        message["In-Reply-To"] = request.in_reply_to
    references = [item for item in request.references if item]
    if references:
        message["References"] = " ".join(references)
    message["X-Mailer"] = "MailOps"
    message.set_content(request.body_text)
    return message_id, message.as_bytes()


def parse_append_provider_ref(mailbox: str, response_data: list[bytes | str], fallback_message_id: str) -> str:
    """Extract a provider-side reference from APPEND response metadata when available."""

    joined = " ".join(
        part.decode("utf-8", "ignore") if isinstance(part, bytes) else str(part)
        for part in response_data
        if part not in (None, b"")
    )
    match = _APPENDUID_RE.search(joined)
    if match is not None:
        return f"{mailbox}:uid:{match.group('uid')}"
    return f"{mailbox}:message-id:{fallback_message_id}"


def parse_draft_provider_ref(provider_ref: str) -> tuple[str, int | None, str | None]:
    """Parse MailOps draft refs such as `Drafts:uid:42` or `Drafts:message-id:<id>`."""

    mailbox, marker, remainder = provider_ref.partition(_UID_REF_MARKER)
    if marker:
        try:
            return mailbox, int(remainder), None
        except ValueError as exc:
            raise ValueError(f"invalid draft UID provider ref: {provider_ref}") from exc

    mailbox, marker, remainder = provider_ref.partition(_MESSAGE_ID_REF_MARKER)
    if marker:
        return mailbox, None, remainder

    raise ValueError(f"unsupported draft provider ref: {provider_ref}")


def _message_id_domain(address: str) -> str | None:
    if "@" not in address:
        return None
    domain = address.split("@", 1)[1].strip().lower()
    return domain or None


def requested_at():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
