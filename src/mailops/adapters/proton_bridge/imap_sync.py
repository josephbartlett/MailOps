"""IMAP sync types and normalization helpers for Proton Bridge."""

from __future__ import annotations

from datetime import datetime, timezone
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.policy import default
from email.utils import getaddresses, parsedate_to_datetime
import hashlib
import re

from pydantic import BaseModel, Field

from mailops.utils.text import compact_whitespace
from mailops.utils.threading import normalize_subject

_UID_RE = re.compile(r"UID\s+(?P<uid>\d+)")
_FLAGS_RE = re.compile(r"FLAGS\s+\((?P<flags>[^)]*)\)")
_INTERNALDATE_RE = re.compile(r'INTERNALDATE\s+"(?P<internaldate>[^"]+)"')
_MESSAGE_ID_RE = re.compile(r"<[^>]+>")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_LIST_RE = re.compile(
    r'^\((?P<attributes>.*?)\)\s+"(?P<delimiter>[^"]*)"\s+(?P<name>".*"|[^\s].*)$'
)


class ImapFolder(BaseModel):
    name: str
    delimiter: str = "/"
    attributes: list[str] = Field(default_factory=list)
    role: str = "unknown"
    is_selectable: bool = True
    can_sync: bool = True
    can_create_draft: bool = False


class ImapSyncRequest(BaseModel):
    account_id: str | None = None
    folders: list[str] = Field(default_factory=list)
    limit: int = 250


class NormalizedImapMessage(BaseModel):
    uid: int
    provider_message_id: str
    provider_thread_id: str
    subject: str
    sender: str
    to_recipients: list[str] = Field(default_factory=list)
    cc_recipients: list[str] = Field(default_factory=list)
    bcc_recipients: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    sent_at: datetime | None = None
    received_at: datetime | None = None
    snippet: str = ""
    body_text: str = ""
    flags: list[str] = Field(default_factory=list)
    unread_count: int = 0
    followup_state: str = "ambiguous"

    def message_record_id(self, account_id: str) -> str:
        return hashlib.sha1(f"{account_id}:{self.provider_message_id}".encode("utf-8")).hexdigest()

    def thread_record_id(self, account_id: str) -> str:
        return hashlib.sha1(f"{account_id}:{self.provider_thread_id}".encode("utf-8")).hexdigest()


def parse_list_response(raw_line: bytes | str) -> ImapFolder:
    """Parse a single IMAP LIST response line."""

    line = raw_line.decode("utf-8", "ignore") if isinstance(raw_line, bytes) else raw_line
    line = line.strip()
    if not line:
        raise ValueError("empty IMAP LIST response")

    match = _LIST_RE.match(line)
    if match is None:
        raise ValueError(f"unexpected IMAP LIST format: {line}")

    raw_attributes = match.group("attributes").strip()
    attributes = [item for item in raw_attributes.split() if item]
    delimiter = match.group("delimiter")
    name = match.group("name").strip()
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]
    role = classify_folder_role(name, attributes)
    is_selectable = not _has_attribute(attributes, "\\Noselect")
    return ImapFolder(
        name=name,
        delimiter=delimiter,
        attributes=attributes,
        role=role,
        is_selectable=is_selectable,
        can_sync=is_selectable,
        can_create_draft=is_selectable and role == "drafts",
    )


def classify_folder_role(name: str, attributes: list[str]) -> str:
    """Classify Proton Bridge folders from provider attributes first, then names."""

    if _has_attribute(attributes, "\\Drafts"):
        return "drafts"
    if _has_attribute(attributes, "\\Sent"):
        return "sent"
    if _has_attribute(attributes, "\\Trash"):
        return "trash"
    if _has_attribute(attributes, "\\Archive"):
        return "archive"
    if _has_attribute(attributes, "\\All"):
        return "all_mail"
    if _has_attribute(attributes, "\\Junk"):
        return "spam"
    if _has_attribute(attributes, "\\Flagged"):
        return "starred"
    if _has_attribute(attributes, "\\Noselect"):
        return "container"

    normalized = name.strip().lower()
    if normalized == "inbox":
        return "inbox"
    if normalized in {"draft", "drafts"}:
        return "drafts"
    if normalized in {"sent", "sent mail"}:
        return "sent"
    if normalized in {"trash", "deleted", "deleted items"}:
        return "trash"
    if normalized in {"archive", "archives"}:
        return "archive"
    if normalized in {"all mail", "all messages"}:
        return "all_mail"
    if normalized in {"spam", "junk"}:
        return "spam"
    if normalized == "starred":
        return "starred"
    if normalized.startswith("labels/"):
        return "label"
    if normalized.startswith("folders/"):
        return "folder"
    return "unknown"


def _has_attribute(attributes: list[str], needle: str) -> bool:
    return any(attribute.lower() == needle.lower() for attribute in attributes)


def parse_search_uids(response_data: list[bytes | str]) -> list[int]:
    """Parse UIDs returned by IMAP SEARCH."""

    if not response_data:
        return []
    first = response_data[0]
    if isinstance(first, bytes):
        raw = first.decode("utf-8", "ignore")
    else:
        raw = first
    raw = raw.strip()
    if not raw:
        return []
    return [int(item) for item in raw.split()]


def parse_fetch_response(fetch_data: list[object]) -> tuple[int, list[str], datetime | None, bytes]:
    """Extract UID, flags, internal date, and message bytes from IMAP FETCH data."""

    for part in fetch_data:
        if not isinstance(part, tuple) or len(part) < 2:
            continue
        metadata = part[0].decode("utf-8", "ignore") if isinstance(part[0], bytes) else str(part[0])
        message_bytes = part[1]
        if not isinstance(message_bytes, (bytes, bytearray)):
            continue

        uid_match = _UID_RE.search(metadata)
        if uid_match is None:
            raise ValueError(f"unable to parse UID from FETCH metadata: {metadata}")

        flags_match = _FLAGS_RE.search(metadata)
        flags = flags_match.group("flags").split() if flags_match is not None and flags_match.group("flags") else []

        internal_date = None
        internal_match = _INTERNALDATE_RE.search(metadata)
        if internal_match is not None:
            internal_date = parsedate_to_datetime(internal_match.group("internaldate"))
            if internal_date.tzinfo is None:
                internal_date = internal_date.replace(tzinfo=timezone.utc)

        return int(uid_match.group("uid")), flags, internal_date, bytes(message_bytes)
    raise ValueError("no message payload found in FETCH response")


def normalize_imap_message(
    *,
    account_id: str,
    account_email: str,
    uid: int,
    raw_message: bytes,
    flags: list[str],
    internal_date: datetime | None,
) -> NormalizedImapMessage:
    """Normalize RFC822 content into MailOps-ready message state."""

    parsed = message_from_bytes(raw_message, policy=default)
    subject = _decode_header_value(parsed.get("Subject", "")) or "(no subject)"
    sender = _extract_primary_address(parsed.get("From", ""))
    to_recipients = _extract_addresses(parsed.get_all("To", []))
    cc_recipients = _extract_addresses(parsed.get_all("Cc", []))
    bcc_recipients = _extract_addresses(parsed.get_all("Bcc", []))
    participants = sorted({item for item in [sender, *to_recipients, *cc_recipients, *bcc_recipients] if item})
    provider_message_id = _canonical_message_id(parsed.get("Message-ID")) or f"uid:{account_id}:{uid}"
    provider_thread_id = _build_provider_thread_id(parsed, subject, provider_message_id)

    sent_at = _parse_header_datetime(parsed.get("Date"))
    received_at = internal_date or sent_at
    body_text = _extract_body_text(parsed)
    snippet = compact_whitespace(body_text)[:240]
    normalized_sender = sender.lower()
    normalized_account = account_email.lower()
    unread_count = 0 if "\\Seen" in flags else 1
    followup_state = "waiting_on_them" if normalized_sender == normalized_account else "waiting_on_me"

    return NormalizedImapMessage(
        uid=uid,
        provider_message_id=provider_message_id,
        provider_thread_id=provider_thread_id,
        subject=subject,
        sender=normalized_sender,
        to_recipients=[item.lower() for item in to_recipients],
        cc_recipients=[item.lower() for item in cc_recipients],
        bcc_recipients=[item.lower() for item in bcc_recipients],
        participants=[item.lower() for item in participants],
        sent_at=sent_at,
        received_at=received_at,
        snippet=snippet,
        body_text=body_text,
        flags=flags,
        unread_count=unread_count,
        followup_state=followup_state,
    )


def _decode_header_value(value: str) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _extract_primary_address(value: str) -> str:
    addresses = _extract_addresses([value])
    if not addresses:
        return ""
    return addresses[0]


def _extract_addresses(values: list[str]) -> list[str]:
    addresses = []
    for _, address in getaddresses(values):
        if address:
            addresses.append(address.strip())
    return addresses


def _canonical_message_id(value: str | None) -> str | None:
    if value is None:
        return None
    match = _MESSAGE_ID_RE.search(value)
    if match is None:
        return value.strip()
    return match.group(0)


def _build_provider_thread_id(parsed: Message, subject: str, provider_message_id: str) -> str:
    references = parsed.get("References", "")
    reference_ids = _MESSAGE_ID_RE.findall(references)
    if reference_ids:
        thread_anchor = reference_ids[0]
    else:
        in_reply_to = _canonical_message_id(parsed.get("In-Reply-To"))
        thread_anchor = in_reply_to or normalize_subject(subject).lower() or provider_message_id
    return hashlib.sha1(thread_anchor.encode("utf-8")).hexdigest()


def _parse_header_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _extract_body_text(parsed: Message) -> str:
    text_parts: list[str] = []
    html_parts: list[str] = []

    if parsed.is_multipart():
        for part in parsed.walk():
            if part.is_multipart():
                continue
            if part.get_content_disposition() == "attachment":
                continue
            content_type = part.get_content_type()
            payload = part.get_content()
            if not isinstance(payload, str):
                continue
            if content_type == "text/plain":
                text_parts.append(payload)
            elif content_type == "text/html":
                html_parts.append(payload)
    else:
        payload = parsed.get_content()
        if isinstance(payload, str):
            if parsed.get_content_type() == "text/html":
                html_parts.append(payload)
            else:
                text_parts.append(payload)

    if text_parts:
        return compact_whitespace("\n\n".join(text_parts))
    if html_parts:
        return compact_whitespace(_HTML_TAG_RE.sub(" ", "\n\n".join(html_parts)))
    return ""
