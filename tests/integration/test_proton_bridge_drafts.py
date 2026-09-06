from __future__ import annotations

from email import message_from_bytes
from pydantic import SecretStr
import pytest

from mailops.adapters.proton_bridge.adapter import ProtonBridgeAdapter
from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.adapters.proton_bridge.drafts import DraftCreateRequest, parse_append_provider_ref, parse_draft_reference
from mailops.core.config import AppConfig
from mailops.core.exceptions import AdapterError


class FakeDraftImapClient:
    def __init__(self) -> None:
        self.login_calls: list[tuple[str, str]] = []
        self.append_calls: list[tuple[str, str, bytes]] = []

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        self.login_calls.append((username, password))
        return "OK", [b"logged in"]

    def list(self) -> tuple[str, list[bytes]]:
        return "OK", [b'(\\HasNoChildren \\Drafts) "/" "Drafts"', b'(\\HasNoChildren) "/" "INBOX"']

    def append(self, mailbox: str, flags: str, date_time: object, raw_message: bytes) -> tuple[str, list[bytes]]:
        self.append_calls.append((mailbox, flags, raw_message))
        return "OK", [b"[APPENDUID 7 42] APPEND completed"]

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b"logged out"]


def test_proton_bridge_create_draft_appends_rfc822_message_to_drafts(tmp_path) -> None:
    client = FakeDraftImapClient()
    config = AppConfig(home_dir=tmp_path / ".mailops")
    adapter = ProtonBridgeAdapter(config, imap_client_factory=lambda endpoint: client)

    assert adapter.capabilities.sync is True
    assert adapter.capabilities.drafts is True
    assert adapter.capabilities.send is False
    assert adapter.capabilities.labels is False
    assert adapter.capabilities.rules is False

    result = adapter.create_draft(
        DraftCreateRequest(
            account_id="ops@example.com",
            from_address="ops@example.com",
            to_recipients=["client@example.com"],
            subject="Re: Scheduling next steps",
            body_text="I can meet tomorrow afternoon.",
            in_reply_to="<source-message@example.com>",
            references=["<source-message@example.com>"],
        ),
        overrides=BridgeDiscoveryOverrides(
            username="bridge-user",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
        ),
    )

    assert result.mailbox == "Drafts"
    reference = parse_draft_reference(result.provider_ref)
    assert reference.mailbox == "Drafts"
    assert reference.uid == 42
    assert reference.uid_validity == "7"
    assert reference.message_id == result.message_id
    assert client.login_calls == [("bridge-user", "bridge-pass")]
    assert len(client.append_calls) == 1

    mailbox, flags, raw_message = client.append_calls[0]
    assert mailbox == "Drafts"
    assert flags == r"(\Draft)"

    parsed = message_from_bytes(raw_message)
    assert parsed["From"] == "ops@example.com"
    assert parsed["To"] == "client@example.com"
    assert parsed["Subject"] == "Re: Scheduling next steps"
    assert parsed["In-Reply-To"] == "<source-message@example.com>"
    assert parsed["References"] == "<source-message@example.com>"
    assert "I can meet tomorrow afternoon." in parsed.get_payload()


class DraftLookupClient(FakeDraftImapClient):
    def __init__(self, *, epoch="7", message_id="<draft@example.com>", matches=b"77"):
        super().__init__()
        self.epoch = epoch
        self.message_id = message_id
        self.matches = matches
        self.fetches = []
        self.searches = []

    def select(self, mailbox, readonly=False):
        assert readonly is True
        return "OK", [b"1"]

    def response(self, code):
        return code, [self.epoch.encode("ascii")]

    def uid(self, command, *args):
        if command == "SEARCH":
            self.searches.append(args)
            return "OK", [self.matches]
        assert command == "FETCH"
        assert "BODY.PEEK[HEADER.FIELDS" in args[1]
        self.fetches.append(int(args[0]))
        headers = f"Message-ID: {self.message_id}\nFrom: ops@example.com\nSubject: Draft\n\n".encode()
        metadata = f'{args[0]} (UID {args[0]} FLAGS (\\Draft) INTERNALDATE "10-Apr-2026 01:26:04 +0000")'.encode()
        return "OK", [(metadata, headers)]


def _lookup(tmp_path, client, provider_ref):
    return ProtonBridgeAdapter(AppConfig(home_dir=tmp_path), imap_client_factory=lambda endpoint: client).lookup_draft(
        account_id="ops@example.com", provider_ref=provider_ref,
        overrides=BridgeDiscoveryOverrides(username="ops@example.com", password=SecretStr("bridge-pass")),
    )


def test_draft_lookup_after_epoch_reset_searches_stable_message_id(tmp_path):
    reference = parse_append_provider_ref("Drafts", [b"[APPENDUID 7 42]"], "<draft@example.com>")
    client = DraftLookupClient(epoch="8")
    result = _lookup(tmp_path, client, reference)
    assert result.status == "present"
    assert result.uid == 77
    assert client.fetches == [77]
    assert client.searches[0][-1] == "<draft@example.com>"


def test_draft_lookup_checks_message_id_even_when_epoch_matches(tmp_path):
    reference = parse_append_provider_ref("Drafts", [b"[APPENDUID 7 42]"], "<draft@example.com>")
    with pytest.raises(AdapterError, match="different Message-ID"):
        _lookup(tmp_path, DraftLookupClient(message_id="<unrelated@example.com>"), reference)


def test_ambiguous_draft_message_id_does_not_select_arbitrary_match(tmp_path):
    reference = parse_append_provider_ref("Drafts", [], "<draft@example.com>")
    client = DraftLookupClient(matches=b"77 78")
    with pytest.raises(AdapterError, match="multiple messages"):
        _lookup(tmp_path, client, reference)
    assert client.fetches == []


def test_legacy_uid_only_draft_reference_is_unverified_without_provider_access(tmp_path):
    client = DraftLookupClient()
    result = _lookup(tmp_path, client, "Drafts:uid:42")
    assert result.status == "unverified"
    assert client.login_calls == []


def test_invalid_draft_reference_rejected_before_login(tmp_path):
    client = DraftLookupClient()
    with pytest.raises(AdapterError, match="Invalid Proton draft"):
        _lookup(tmp_path, client, "invalid")
    assert client.login_calls == []
