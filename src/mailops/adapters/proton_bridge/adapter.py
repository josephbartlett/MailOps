"""Proton Bridge adapter implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from email import message_from_bytes
from email.policy import default
import imaplib
from typing import Callable

from mailops.adapters.base import AdapterCapabilities
from mailops.adapters.proton_bridge.bridge_discovery import (
    BridgeDiscoveryOverrides,
    BridgeEndpoint,
    discover_bridge,
)
from mailops.adapters.proton_bridge.drafts import (
    DraftCreateRequest,
    DraftCreateResult,
    DraftLookupResult,
    build_draft_message,
    parse_append_provider_ref,
    parse_draft_provider_ref,
)
from mailops.adapters.proton_bridge.imap_sync import (
    ImapFolder,
    ImapSyncRequest,
    _canonical_message_id,
    _decode_header_value,
    _extract_addresses,
    _extract_primary_address,
    normalize_imap_message,
    parse_fetch_response,
    parse_list_response,
    parse_search_uids,
)
from mailops.adapters.proton_bridge.networking import bridge_host_candidates
from mailops.core.config import AppConfig
from mailops.core.exceptions import AdapterError
from mailops.core.models import SyncResult
from mailops.index.db import (
    connect_db,
    get_folder_last_uid,
    initialize_database,
    link_message_to_folder,
    upsert_account,
    upsert_account_alias,
    upsert_folder,
    upsert_message,
    upsert_thread,
)
from mailops.index.triage import refresh_thread_triage

DEFAULT_SYNC_FOLDERS = ("INBOX",)
BRIDGE_CONNECT_TIMEOUT_SECONDS = 2.0


class ProtonBridgeAdapter:
    """Provider-aware implementation for local Proton Bridge IMAP workflows."""

    provider_name = "proton_bridge"
    capabilities = AdapterCapabilities(sync=True, drafts=True, send=False, labels=False, rules=False)

    def __init__(
        self,
        config: AppConfig,
        *,
        imap_client_factory: Callable[[BridgeEndpoint], object] | None = None,
    ) -> None:
        self.config = config
        self._imap_client_factory = imap_client_factory

    def describe(self) -> str:
        return "Proton Bridge adapter for local IMAP/SMTP workflows."

    def discover(self, *, overrides: BridgeDiscoveryOverrides | None = None) -> BridgeEndpoint:
        return discover_bridge(self.config, overrides=overrides)

    def list_folders(self, *, overrides: BridgeDiscoveryOverrides | None = None) -> list[ImapFolder]:
        endpoint = self.discover(overrides=overrides)
        client = self._login(endpoint)
        try:
            status, data = client.list()
            if status != "OK":
                raise AdapterError("Proton Bridge IMAP LIST failed.")
            return [parse_list_response(item) for item in data if item]
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"Proton Bridge folder listing failed: {exc}") from exc
        finally:
            self._logout(client)

    def create_draft(
        self,
        request: DraftCreateRequest,
        *,
        overrides: BridgeDiscoveryOverrides | None = None,
    ) -> DraftCreateResult:
        """Create a provider-side draft via Proton Bridge IMAP APPEND."""

        endpoint = self.discover(overrides=overrides)
        client = self._login(endpoint)
        try:
            status, data = client.list()
            if status != "OK":
                raise AdapterError("Proton Bridge IMAP LIST failed while resolving the Drafts mailbox.")
            folders = [parse_list_response(item) for item in data if item]
            drafts_folder = self._resolve_drafts_folder(folders)
            message_id, raw_message = build_draft_message(request)
            status, append_data = client.append(self._imap_mailbox_name(drafts_folder.name), r"(\Draft)", None, raw_message)
            if status != "OK":
                raise AdapterError(f"Proton Bridge draft APPEND failed for '{drafts_folder.name}'.")
            provider_ref = parse_append_provider_ref(drafts_folder.name, append_data, message_id)
            return DraftCreateResult(
                account_id=request.account_id,
                mailbox=drafts_folder.name,
                provider_ref=provider_ref,
                message_id=message_id,
            )
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"Proton Bridge draft creation failed: {exc}") from exc
        finally:
            self._logout(client)

    def lookup_draft(
        self,
        *,
        account_id: str,
        provider_ref: str,
        overrides: BridgeDiscoveryOverrides | None = None,
    ) -> DraftLookupResult:
        """Resolve a MailOps provider draft ref back to Proton Drafts metadata."""

        endpoint = self.discover(overrides=overrides)
        client = self._login(endpoint)
        mailbox, uid, message_id = parse_draft_provider_ref(provider_ref)
        try:
            status, _ = client.select(self._imap_mailbox_name(mailbox), readonly=True)
            if status != "OK":
                raise AdapterError(f"Unable to select Proton draft mailbox '{mailbox}'.")
            resolved_uid = uid
            if resolved_uid is None and message_id:
                status, search_data = client.uid("SEARCH", "HEADER", "Message-ID", message_id)
                if status != "OK":
                    raise AdapterError(f"Unable to search Proton draft mailbox '{mailbox}'.")
                matches = parse_search_uids(search_data)
                resolved_uid = matches[0] if matches else None
            if resolved_uid is None:
                return DraftLookupResult(
                    account_id=account_id,
                    provider_ref=provider_ref,
                    mailbox=mailbox,
                    provider_message_id=message_id,
                    status="missing",
                )

            status, fetch_data = client.uid(
                "FETCH",
                str(resolved_uid),
                "(UID FLAGS INTERNALDATE BODY.PEEK[HEADER.FIELDS (MESSAGE-ID FROM TO CC BCC SUBJECT DATE)])",
            )
            if status != "OK":
                raise AdapterError(f"Unable to fetch Proton draft UID {resolved_uid} from '{mailbox}'.")
            try:
                fetched_uid, flags, internal_date, raw_headers = parse_fetch_response(fetch_data)
            except ValueError:
                return DraftLookupResult(
                    account_id=account_id,
                    provider_ref=provider_ref,
                    mailbox=mailbox,
                    uid=resolved_uid,
                    provider_message_id=message_id,
                    status="missing",
                )

            parsed = message_from_bytes(raw_headers, policy=default)
            return DraftLookupResult(
                account_id=account_id,
                provider_ref=provider_ref,
                mailbox=mailbox,
                uid=fetched_uid,
                provider_message_id=_canonical_message_id(parsed.get("Message-ID")) or message_id,
                subject=_decode_header_value(parsed.get("Subject", "")) or "(no subject)",
                from_address=_extract_primary_address(parsed.get("From", "")).lower(),
                to_recipients=[item.lower() for item in _extract_addresses(parsed.get_all("To", []))],
                cc_recipients=[item.lower() for item in _extract_addresses(parsed.get_all("Cc", []))],
                bcc_recipients=[item.lower() for item in _extract_addresses(parsed.get_all("Bcc", []))],
                flags=flags,
                internal_date=internal_date,
                status="present",
            )
        except AdapterError:
            raise
        except ValueError as exc:
            raise AdapterError(str(exc)) from exc
        except Exception as exc:
            raise AdapterError(f"Proton Bridge draft lookup failed: {exc}") from exc
        finally:
            self._logout(client)

    def sync(self, request: ImapSyncRequest, *, overrides: BridgeDiscoveryOverrides | None = None) -> SyncResult:
        endpoint = self.discover(overrides=overrides)
        account_id = request.account_id or endpoint.resolved_account_id()
        account_email = endpoint.account_email or endpoint.username or account_id
        result = SyncResult(account_id=account_id, provider=self.provider_name)

        client = self._login(endpoint)
        try:
            status, data = client.list()
            if status != "OK":
                raise AdapterError("Proton Bridge IMAP LIST failed.")
            folders = [parse_list_response(item) for item in data if item]
            result.folders_discovered = [folder.name for folder in folders]

            target_folders = self._resolve_target_folders(folders, request.folders)
            sync_timestamp = datetime.now(timezone.utc).isoformat()
            initialize_database(self.config)

            with connect_db(self.config.db_path) as connection:
                upsert_account(
                    connection,
                    account_id=account_id,
                    provider=self.provider_name,
                    display_name=account_id,
                    email_address=account_id,
                    adapter_config_ref=endpoint.profile_name,
                    last_sync_at=sync_timestamp,
                    sync_status="ready",
                )
                self._record_account_aliases(
                    connection,
                    account_id=account_id,
                    endpoint_username=endpoint.username,
                    endpoint_account_email=endpoint.account_email,
                )

                for folder in target_folders:
                    folder_id = self._folder_record_id(account_id, folder.name)
                    prior_last_uid = get_folder_last_uid(connection, folder_id)
                    upsert_folder(
                        connection,
                        folder_id=folder_id,
                        account_id=account_id,
                        provider_folder_id=folder.name,
                        display_name=folder.name,
                        delimiter=folder.delimiter,
                        attributes=folder.attributes,
                        role=folder.role,
                        is_selectable=folder.is_selectable,
                        can_sync=folder.can_sync,
                        can_create_draft=folder.can_create_draft,
                    )

                    status, select_data = client.select(self._imap_mailbox_name(folder.name), readonly=True)
                    if status != "OK":
                        result.errors.append(f"Failed to select folder '{folder.name}'.")
                        continue
                    message_count = self._parse_exists_count(select_data)

                    search_query = "ALL" if prior_last_uid == 0 else f"UID {prior_last_uid + 1}:*"
                    status, search_data = client.uid("SEARCH", search_query)
                    if status != "OK":
                        result.errors.append(f"Failed to search folder '{folder.name}'.")
                        continue

                    all_uids = parse_search_uids(search_data)
                    if not all_uids:
                        if message_count == 0:
                            result.warnings.append(f"Folder '{folder.name}' currently reports 0 messages.")
                        elif message_count is not None:
                            result.warnings.append(
                                f"Folder '{folder.name}' reports {message_count} messages, but Bridge returned 0 search results."
                            )
                    selected_uids, warning = self._select_uids(all_uids, prior_last_uid, request.limit, folder.name)
                    if warning is not None:
                        result.warnings.append(warning)

                    latest_uid = prior_last_uid
                    failed_fetch_uids: list[int] = []
                    for uid in selected_uids:
                        status, fetch_data = client.uid("FETCH", str(uid), "(UID FLAGS INTERNALDATE RFC822)")
                        if status != "OK":
                            result.errors.append(f"Failed to fetch UID {uid} from '{folder.name}'.")
                            failed_fetch_uids.append(uid)
                            continue

                        try:
                            parsed_uid, flags, internal_date, raw_message = parse_fetch_response(fetch_data)
                        except ValueError as exc:
                            result.errors.append(f"Failed to parse UID {uid} from '{folder.name}': {exc}")
                            failed_fetch_uids.append(uid)
                            continue
                        normalized = normalize_imap_message(
                            account_id=account_id,
                            account_email=account_email,
                            uid=parsed_uid,
                            raw_message=raw_message,
                            flags=flags,
                            internal_date=internal_date,
                        )
                        thread_id = normalized.thread_record_id(account_id)
                        message_id = normalized.message_record_id(account_id)
                        last_message_at = (
                            normalized.received_at.isoformat()
                            if normalized.received_at is not None
                            else normalized.sent_at.isoformat() if normalized.sent_at is not None else None
                        )

                        upsert_thread(
                            connection,
                            thread_id=thread_id,
                            account_id=account_id,
                            provider_thread_id=normalized.provider_thread_id,
                            subject=normalized.subject,
                            participants=normalized.participants,
                            last_message_at=last_message_at,
                            unread_count=normalized.unread_count,
                            importance_score=0.0,
                            followup_state=normalized.followup_state,
                            classification_tags=[],
                        )
                        inserted = upsert_message(
                            connection,
                            message_id=message_id,
                            provider_message_id=normalized.provider_message_id,
                            thread_id=thread_id,
                            sender=normalized.sender,
                            to_recipients=normalized.to_recipients,
                            cc_recipients=normalized.cc_recipients,
                            bcc_recipients=normalized.bcc_recipients,
                            sent_at=normalized.sent_at.isoformat() if normalized.sent_at is not None else None,
                            received_at=normalized.received_at.isoformat() if normalized.received_at is not None else None,
                            snippet=normalized.snippet,
                            body_text=normalized.body_text,
                            folder_or_label_refs=[folder.name],
                            flags=normalized.flags,
                        )
                        link_message_to_folder(
                            connection,
                            folder_id=folder_id,
                            provider_message_id=normalized.provider_message_id,
                            uid=normalized.uid,
                            flags=normalized.flags,
                        )

                        if inserted:
                            result.messages_indexed += 1
                        latest_uid = max(latest_uid, normalized.uid)

                    if failed_fetch_uids:
                        earliest_failed_uid = min(failed_fetch_uids)
                        latest_uid = max(prior_last_uid, earliest_failed_uid - 1)
                        result.warnings.append(
                            f"Cursor for '{folder.name}' was not advanced past failed UID {earliest_failed_uid}; run sync again to retry."
                        )

                    upsert_folder(
                        connection,
                        folder_id=folder_id,
                        account_id=account_id,
                        provider_folder_id=folder.name,
                        display_name=folder.name,
                        delimiter=folder.delimiter,
                        attributes=folder.attributes,
                        role=folder.role,
                        is_selectable=folder.is_selectable,
                        can_sync=folder.can_sync,
                        can_create_draft=folder.can_create_draft,
                        last_uid=latest_uid,
                        last_sync_at=sync_timestamp,
                    )
                    result.folders_synced.append(folder.name)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"Proton Bridge sync failed: {exc}") from exc
        finally:
            self._logout(client)

        refresh_thread_triage(self.config, account_id=account_id)
        if not result.folders_synced and not result.errors:
            result.warnings.append("No folders were synced.")
        return result

    def _login(self, endpoint: BridgeEndpoint) -> object:
        if not endpoint.is_usable():
            raise AdapterError(
                "Proton Bridge credentials are incomplete. Provide username and password via config, env, or CLI."
            )

        password = endpoint.password.get_secret_value() if endpoint.password is not None else ""
        connection_errors: list[str] = []
        for candidate in self._endpoint_candidates(endpoint):
            try:
                client = self._build_imap_client(candidate)
            except OSError as exc:
                connection_errors.append(f"{candidate.host}:{candidate.imap_port} ({exc})")
                continue
            try:
                client.login(candidate.username, password)
            except Exception as exc:
                self._logout(client)
                raise AdapterError(f"Proton Bridge login failed at {candidate.host}:{candidate.imap_port}: {exc}") from exc
            return client

        detail = "; ".join(connection_errors) if connection_errors else f"{endpoint.host}:{endpoint.imap_port}"
        raise AdapterError(f"Proton Bridge IMAP connection failed. Tried: {detail}")

    def _endpoint_candidates(self, endpoint: BridgeEndpoint) -> list[BridgeEndpoint]:
        candidates: list[BridgeEndpoint] = []
        for host in bridge_host_candidates(endpoint.host):
            candidates.append(endpoint.model_copy(update={"host": host}))
        return candidates

    def _build_imap_client(self, endpoint: BridgeEndpoint) -> object:
        if self._imap_client_factory is not None:
            return self._imap_client_factory(endpoint)
        if endpoint.imap_security == "ssl":
            return imaplib.IMAP4_SSL(endpoint.host, endpoint.imap_port, timeout=BRIDGE_CONNECT_TIMEOUT_SECONDS)
        return imaplib.IMAP4(endpoint.host, endpoint.imap_port, timeout=BRIDGE_CONNECT_TIMEOUT_SECONDS)

    def _logout(self, client: object) -> None:
        logout = getattr(client, "logout", None)
        if callable(logout):
            try:
                logout()
            except Exception:
                return

    def _resolve_target_folders(self, available_folders: list[ImapFolder], requested_folders: list[str]) -> list[ImapFolder]:
        if requested_folders:
            requested = {item.lower(): item for item in requested_folders}
            resolved = [folder for folder in available_folders if folder.name.lower() in requested and folder.can_sync]
            if not resolved:
                raise AdapterError("Requested Proton Bridge folders were not found.")
            return resolved

        syncable_folders = [folder for folder in available_folders if folder.can_sync]
        defaults = [folder for folder in syncable_folders if folder.name.upper() in DEFAULT_SYNC_FOLDERS]
        return defaults or syncable_folders[:1]

    def _resolve_drafts_folder(self, available_folders: list[ImapFolder]) -> ImapFolder:
        for folder in available_folders:
            if any(attribute.lower() == "\\drafts" for attribute in folder.attributes):
                return folder

        candidates = {
            "drafts",
            "draft",
        }
        for folder in available_folders:
            if folder.name.strip().lower() in candidates:
                return folder
        raise AdapterError("Unable to resolve a Proton Drafts folder from Bridge metadata.")

    def _select_uids(
        self,
        uids: list[int],
        prior_last_uid: int,
        limit: int,
        folder_name: str,
    ) -> tuple[list[int], str | None]:
        if len(uids) <= limit:
            return uids, None
        if prior_last_uid == 0:
            selected = uids[-limit:]
            return (
                selected,
                f"Initial sync for '{folder_name}' was capped to the most recent {limit} messages.",
            )
        selected = uids[:limit]
        return (
            selected,
            f"Incremental sync for '{folder_name}' was capped to {limit} new messages; run sync again to continue.",
        )

    def _folder_record_id(self, account_id: str, folder_name: str) -> str:
        import hashlib

        return hashlib.sha1(f"{account_id}:{folder_name}".encode("utf-8")).hexdigest()

    def _record_account_aliases(
        self,
        connection: object,
        *,
        account_id: str,
        endpoint_username: str | None,
        endpoint_account_email: str | None,
    ) -> None:
        alias_candidates = {
            alias.strip().lower()
            for alias in (account_id, endpoint_username, endpoint_account_email)
            if alias and alias.strip()
        }
        for alias in alias_candidates:
            upsert_account_alias(
                connection,
                alias_email=alias,
                account_id=account_id,
                provider_username=endpoint_username,
                is_primary=alias == account_id,
            )

    def _parse_exists_count(self, select_data: object) -> int | None:
        if not isinstance(select_data, list) or not select_data:
            return None
        first = select_data[0]
        if isinstance(first, bytes):
            raw_value = first.decode("utf-8", "ignore").strip()
        else:
            raw_value = str(first).strip()
        if raw_value.isdigit():
            return int(raw_value)
        return None

    def _imap_mailbox_name(self, folder_name: str) -> str:
        if any(character.isspace() for character in folder_name) or '"' in folder_name:
            escaped = folder_name.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return folder_name
