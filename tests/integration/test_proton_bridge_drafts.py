from __future__ import annotations

from email import message_from_bytes
from pydantic import SecretStr

from mailops.adapters.proton_bridge.adapter import ProtonBridgeAdapter
from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.adapters.proton_bridge.drafts import DraftCreateRequest
from mailops.core.config import AppConfig


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
    assert result.provider_ref == "Drafts:uid:42"
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
