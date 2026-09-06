from __future__ import annotations

from email.message import EmailMessage

from pydantic import SecretStr
import pytest

from mailops.adapters.proton_bridge.adapter import ProtonBridgeAdapter
from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.adapters.proton_bridge.imap_sync import ImapSyncRequest, classify_folder_role, parse_list_response
from mailops.core.config import AppConfig
from mailops.core.exceptions import AdapterError
from mailops.index.db import connect_db, get_table_counts
from mailops.index.queries import list_unanswered_threads
from mailops.index.search import SearchRequest, search_messages
from mailops.index.triage import summarize_followup_states


def _build_message(
    *,
    message_id: str,
    subject: str,
    sender: str,
    recipient: str,
    body: str,
    date_header: str,
) -> bytes:
    message = EmailMessage()
    message["Message-ID"] = message_id
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message["Date"] = date_header
    message.set_content(body)
    return message.as_bytes()


def _build_multipart_message(
    *,
    message_id: str,
    subject: str,
    sender: str,
    recipient: str,
    text_body: str,
    html_body: str,
    date_header: str,
) -> bytes:
    message = EmailMessage()
    message["Message-ID"] = message_id
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message["Date"] = date_header
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message.as_bytes()


class FakeImapClient:
    def __init__(self) -> None:
        self.mailboxes = {
            "INBOX": {
                1: {
                    "flags": [],
                    "internaldate": "Tue, 07 Apr 2026 10:00:00 +0000",
                    "raw": _build_message(
                        message_id="<message-1@example.com>",
                        subject="Client invoice follow-up",
                        sender="client@example.com",
                        recipient="ops@example.com",
                        body="Checking whether you reviewed the invoice.",
                        date_header="Tue, 07 Apr 2026 09:58:00 +0000",
                    ),
                },
                2: {
                    "flags": [r"\Seen"],
                    "internaldate": "Tue, 08 Apr 2026 11:00:00 +0000",
                    "raw": _build_multipart_message(
                        message_id="<message-2@example.com>",
                        subject="Re: Client invoice follow-up",
                        sender="ops@example.com",
                        recipient="client@example.com",
                        text_body="I reviewed it and sent payment details.",
                        html_body="<p>I reviewed it and sent payment details.</p>",
                        date_header="Tue, 08 Apr 2026 10:59:00 +0000",
                    ),
                },
            }
        }
        self.selected_mailbox = "INBOX"
        self.login_calls: list[tuple[str, str]] = []

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        self.login_calls.append((username, password))
        return "OK", [b"logged in"]

    def list(self) -> tuple[str, list[bytes]]:
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"']

    def select(self, mailbox: str, readonly: bool = True) -> tuple[str, list[bytes]]:
        self.selected_mailbox = mailbox
        return "OK", [b"2"]

    def response(self, code: str) -> tuple[str, list[bytes]]:
        assert code == "UIDVALIDITY"
        return code, [b"100"]

    def uid(self, command: str, *args: object) -> tuple[str, list[object]]:
        mailbox = self.mailboxes[self.selected_mailbox]
        if command == "SEARCH":
            criteria = str(args[-1])
            if criteria == "ALL":
                uids = sorted(mailbox)
            else:
                start = int(criteria.split(" ")[1].split(":")[0])
                uids = [uid for uid in sorted(mailbox) if uid >= start]
            return "OK", [" ".join(str(uid) for uid in uids).encode("utf-8")]

        if command == "FETCH":
            assert "BODY.PEEK[]" in str(args[1])
            uid = int(args[0])
            message = mailbox[uid]
            metadata = (
                f'{uid} (UID {uid} FLAGS ({" ".join(message["flags"])}) '
                f'INTERNALDATE "{message["internaldate"]}" RFC822 {{{len(message["raw"])}}})'
            ).encode("utf-8")
            return "OK", [(metadata, message["raw"])]

        raise AssertionError(f"Unexpected IMAP command: {command}")

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b"logged out"]


def test_proton_bridge_sync_indexes_messages_and_folders(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    adapter = ProtonBridgeAdapter(config, imap_client_factory=lambda endpoint: FakeImapClient())
    result = adapter.sync(
        ImapSyncRequest(folders=["INBOX"], limit=25),
        overrides=BridgeDiscoveryOverrides(
            username="bridge-user",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
        ),
    )

    counts = get_table_counts(config)
    assert result.errors == []
    assert result.folders_synced == ["INBOX"]
    assert result.messages_indexed == 2
    assert counts["accounts"] == 1
    assert counts["account_aliases"] == 2
    assert counts["folders"] == 1
    assert counts["messages"] == 2
    assert counts["folder_messages"] == 2

    search_results = search_messages(config, SearchRequest(query="invoice"))
    assert len(search_results) == 2

    unanswered = list_unanswered_threads(config, older_than_days=0, account_id="all")
    assert unanswered == []
    summary = summarize_followup_states(config, account_id="all")
    assert summary["waiting_on_them"] == 1

    with connect_db(config.db_path) as connection:
        folder_row = connection.execute("SELECT last_uid, role, is_selectable, can_sync FROM folders").fetchone()
    assert folder_row is not None
    assert int(folder_row["last_uid"]) == 2
    assert folder_row["role"] == "inbox"
    assert int(folder_row["is_selectable"]) == 1
    assert int(folder_row["can_sync"]) == 1


def test_initial_sync_caps_to_recent_window(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    adapter = ProtonBridgeAdapter(config, imap_client_factory=lambda endpoint: FakeImapClient())
    result = adapter.sync(
        ImapSyncRequest(folders=["INBOX"], limit=1),
        overrides=BridgeDiscoveryOverrides(
            username="bridge-user",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
        ),
    )

    assert result.messages_indexed == 1
    assert any("most recent 1 messages" in warning for warning in result.warnings)


class FetchFailureImapClient(FakeImapClient):
    def __init__(self) -> None:
        super().__init__()
        self.mailboxes["INBOX"][3] = {
            "flags": [],
            "internaldate": "Thu, 09 Apr 2026 12:00:00 +0000",
            "raw": _build_message(
                message_id="<message-3@example.com>",
                subject="Follow-up after failed fetch",
                sender="client@example.com",
                recipient="ops@example.com",
                body="This message should not move the cursor past the failed UID.",
                date_header="Thu, 09 Apr 2026 11:58:00 +0000",
            ),
        }

    def uid(self, command: str, *args: object) -> tuple[str, list[object]]:
        if command == "FETCH" and int(args[0]) == 2:
            return "NO", []
        return super().uid(command, *args)


def test_sync_does_not_advance_cursor_past_failed_fetch_uid(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    adapter = ProtonBridgeAdapter(config, imap_client_factory=lambda endpoint: FetchFailureImapClient())

    result = adapter.sync(
        ImapSyncRequest(folders=["INBOX"], limit=25),
        overrides=BridgeDiscoveryOverrides(
            username="bridge-user",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
        ),
    )

    assert result.messages_indexed == 2
    assert result.errors == ["Failed to fetch UID 2 from 'INBOX'."]
    assert any("not advanced past failed UID 2" in warning for warning in result.warnings)

    with connect_db(config.db_path) as connection:
        folder_row = connection.execute("SELECT last_uid FROM folders").fetchone()

    assert folder_row is not None
    assert int(folder_row["last_uid"]) == 1


def test_alias_sync_can_share_one_canonical_account(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    adapter = ProtonBridgeAdapter(config, imap_client_factory=lambda endpoint: FakeImapClient())

    adapter.sync(
        ImapSyncRequest(folders=["INBOX"], limit=25),
        overrides=BridgeDiscoveryOverrides(
            username="primary-login@example.com",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
            canonical_email="ops@example.com",
        ),
    )
    adapter.sync(
        ImapSyncRequest(folders=["INBOX"], limit=25),
        overrides=BridgeDiscoveryOverrides(
            username="alias-login@example.com",
            password=SecretStr("bridge-pass"),
            account_email="info@example.com",
            canonical_email="ops@example.com",
        ),
    )

    counts = get_table_counts(config)
    assert counts["accounts"] == 1
    assert counts["messages"] == 2
    assert counts["threads"] == 1
    assert counts["account_aliases"] == 4


class SingleInboundImapClient(FakeImapClient):
    def __init__(self) -> None:
        self.mailboxes = {
            "INBOX": {
                1: {
                    "flags": [],
                    "internaldate": "Tue, 08 Apr 2026 10:00:00 +0000",
                    "raw": _build_message(
                        message_id="<message-3@example.com>",
                        subject="Payment follow-up",
                        sender="client@example.com",
                        recipient="ops@example.com",
                        body="Can you confirm payment today?",
                        date_header="Tue, 08 Apr 2026 09:58:00 +0000",
                    ),
                }
            }
        }
        self.selected_mailbox = "INBOX"
        self.login_calls = []


def test_proton_bridge_sync_refreshes_waiting_on_me_thread_state(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    adapter = ProtonBridgeAdapter(config, imap_client_factory=lambda endpoint: SingleInboundImapClient())
    adapter.sync(
        ImapSyncRequest(folders=["INBOX"], limit=25),
        overrides=BridgeDiscoveryOverrides(
            username="bridge-user",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
        ),
    )

    unanswered = list_unanswered_threads(config, older_than_days=0, account_id="all")
    assert len(unanswered) == 1
    assert unanswered[0]["followup_state"] == "waiting_on_me"
    assert float(unanswered[0]["importance_score"]) >= 0.9
    assert "direct to you" in unanswered[0]["classification_tags"]


class FolderListClient:
    def __init__(self) -> None:
        self.login_calls: list[tuple[str, str]] = []

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        self.login_calls.append((username, password))
        return "OK", [b"logged in"]

    def list(self) -> tuple[str, list[bytes]]:
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"']

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b"logged out"]


def test_proton_bridge_retries_wsl_windows_host_when_localhost_connection_fails(tmp_path, monkeypatch) -> None:
    import mailops.adapters.proton_bridge.adapter as adapter_module

    config = AppConfig(home_dir=tmp_path / ".mailops")
    attempted_hosts: list[str] = []
    fallback_client = FolderListClient()

    def fake_client_factory(endpoint):
        attempted_hosts.append(endpoint.host)
        if endpoint.host == "127.0.0.1":
            raise OSError("connection refused")
        return fallback_client

    monkeypatch.setattr(
        adapter_module,
        "bridge_host_candidates",
        lambda host: ["127.0.0.1", "172.28.96.1"],
    )

    adapter = ProtonBridgeAdapter(config, imap_client_factory=fake_client_factory)
    folders = adapter.list_folders(
        overrides=BridgeDiscoveryOverrides(
            username="bridge-user",
            password=SecretStr("bridge-pass"),
            account_email="ops@example.com",
        ),
    )

    assert [folder.name for folder in folders] == ["INBOX"]
    assert attempted_hosts == ["127.0.0.1", "172.28.96.1"]
    assert fallback_client.login_calls == [("bridge-user", "bridge-pass")]


def test_proton_folder_capabilities_prefer_attributes() -> None:
    drafts = parse_list_response(b'(\\HasNoChildren \\Drafts) "/" "Custom Draft Box"')
    sent = parse_list_response(b'(\\HasNoChildren \\Sent) "/" "Outgoing"')
    labels = parse_list_response(b'(\\Noselect) "/" "Labels"')

    assert drafts.role == "drafts"
    assert drafts.can_create_draft is True
    assert sent.role == "sent"
    assert sent.can_create_draft is False
    assert labels.role == "container"
    assert labels.is_selectable is False
    assert labels.can_sync is False


def test_proton_folder_capabilities_fall_back_to_names() -> None:
    assert classify_folder_role("All Mail", []) == "all_mail"
    assert classify_folder_role("Labels/Finance", []) == "label"
    assert classify_folder_role("Folders/Clients", []) == "folder"


def _sync_with_client(config, client, *, account="ops@example.com", limit=25):
    return ProtonBridgeAdapter(config, imap_client_factory=lambda endpoint: client).sync(
        ImapSyncRequest(folders=["INBOX"], limit=limit),
        overrides=BridgeDiscoveryOverrides(
            username=account, password=SecretStr("bridge-pass"), account_email=account,
        ),
    )


def test_same_message_id_in_two_accounts_preserves_both_accounts(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    _sync_with_client(config, FakeImapClient())
    result = _sync_with_client(config, FakeImapClient(), account="second@example.com")
    assert result.messages_indexed == 2
    with connect_db(config.db_path) as connection:
        rows = connection.execute(
            """SELECT messages.account_id, threads.account_id AS thread_account, folders.account_id AS folder_account
            FROM messages JOIN threads ON threads.id = messages.thread_id
            JOIN folder_messages ON folder_messages.message_id = messages.id
            JOIN folders ON folders.id = folder_messages.folder_id"""
        ).fetchall()
    assert len(rows) == 4
    assert all(row["account_id"] == row["thread_account"] == row["folder_account"] for row in rows)
    assert len(search_messages(config, SearchRequest(query="invoice", account_id="ops@example.com"))) == 2


def test_uidvalidity_change_restarts_bounded_slice_and_retains_history(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    _sync_with_client(config, FakeImapClient())

    class ResetClient(SingleInboundImapClient):
        def response(self, code):
            return code, [b"200"]

    result = _sync_with_client(config, ResetClient(), limit=1)
    assert result.messages_indexed == 1
    assert any("UIDVALIDITY" in warning for warning in result.warnings)
    with connect_db(config.db_path) as connection:
        folder = connection.execute("SELECT last_uid, uid_validity FROM folders").fetchone()
        assert tuple(folder) == (1, "200")
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM folder_messages").fetchone()[0] == 1


def test_missing_uidvalidity_cannot_advance_a_cursor(tmp_path) -> None:
    class MissingValidityClient(FakeImapClient):
        def response(self, code):
            return code, [None]

    config = AppConfig(home_dir=tmp_path / ".mailops")
    result = _sync_with_client(config, MissingValidityClient())
    assert result.messages_indexed == 0
    assert any("UIDVALIDITY" in error for error in result.errors)
    with connect_db(config.db_path) as connection:
        assert connection.execute("SELECT last_uid FROM folders").fetchone()[0] == 0
        assert connection.execute("SELECT sync_status FROM accounts").fetchone()[0] == "failed"


def test_reversed_imap_range_does_not_refetch_last_message(tmp_path) -> None:
    class ReversedRangeClient(FakeImapClient):
        def uid(self, command, *args):
            if command == "SEARCH" and args[-1] != "ALL":
                return "OK", [b"2"]
            if command == "FETCH":
                raise AssertionError("Already indexed UID must not be refetched")
            return super().uid(command, *args)

    config = AppConfig(home_dir=tmp_path / ".mailops")
    _sync_with_client(config, FakeImapClient())
    result = _sync_with_client(config, ReversedRangeClient())
    assert result.messages_indexed == 0
    assert result.errors == []
    assert result.warnings == []


def test_fetch_uid_mismatch_is_retried_without_advancing_cursor(tmp_path) -> None:
    class WrongUidClient(FakeImapClient):
        def uid(self, command, *args):
            status, data = super().uid(command, *args)
            if command == "FETCH" and args[0] == "1":
                metadata, body = data[0]
                return status, [(metadata.replace(b"UID 1 ", b"UID 99 "), body)]
            return status, data

    config = AppConfig(home_dir=tmp_path / ".mailops")
    result = _sync_with_client(config, WrongUidClient())
    assert len(result.errors) == 1
    with connect_db(config.db_path) as connection:
        assert connection.execute("SELECT last_uid FROM folders").fetchone()[0] == 0
        assert connection.execute("SELECT uid FROM folder_messages").fetchone()[0] == 2


def test_malformed_date_does_not_abort_sync(tmp_path) -> None:
    client = FakeImapClient()
    client.mailboxes["INBOX"][1]["raw"] = client.mailboxes["INBOX"][1]["raw"].replace(
        b"Date: Tue, 07 Apr 2026 09:58:00 +0000", b"Date: invalid"
    )
    result = _sync_with_client(AppConfig(home_dir=tmp_path / ".mailops"), client)
    assert result.messages_indexed == 2
    assert result.errors == []


def test_failed_first_uid_is_not_skipped_when_new_mail_arrives(tmp_path):
    class FirstFetchFails(FakeImapClient):
        def uid(self, command, *args):
            if command == "FETCH" and args[0] == "1":
                return "NO", []
            return super().uid(command, *args)

    config = AppConfig(home_dir=tmp_path / ".mailops")
    _sync_with_client(config, FirstFetchFails(), limit=2)
    client = FetchFailureImapClient()
    # New UID 3 arrives, but a two-message retry must start at failed UID 1.
    result = _sync_with_client(config, client, limit=2)
    assert result.messages_indexed == 1
    with connect_db(config.db_path) as connection:
        assert [row[0] for row in connection.execute("SELECT uid FROM folder_messages ORDER BY uid")] == [1, 2]


def test_missing_message_id_uses_content_identity_not_folder_local_uid(tmp_path):
    from mailops.adapters.proton_bridge.imap_sync import normalize_imap_message

    first = b"From: sender@example.com\nSubject: First\n\nFirst message"
    second = b"From: sender@example.com\nSubject: Second\n\nSecond message"
    messages = [normalize_imap_message(
        account_id="ops@example.com", account_email="ops@example.com", uid=1,
        raw_message=raw, flags=[], internal_date=None,
    ) for raw in (first, second)]
    assert messages[0].provider_message_id != messages[1].provider_message_id


def test_sync_account_mismatch_fails_before_login(tmp_path):
    client = FakeImapClient()
    adapter = ProtonBridgeAdapter(AppConfig(home_dir=tmp_path), imap_client_factory=lambda endpoint: client)
    with pytest.raises(AdapterError, match="does not match"):
        adapter.sync(
            ImapSyncRequest(account_id="wrong@example.com"),
            overrides=BridgeDiscoveryOverrides(username="ops@example.com", password=SecretStr("password")),
        )
    assert client.login_calls == []
