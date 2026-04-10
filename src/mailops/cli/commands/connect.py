"""Implementation of `mailops connect`."""

import typer

from rich.table import Table

from mailops.adapters.proton_bridge.adapter import ProtonBridgeAdapter
from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.adapters.proton_bridge.registry import (
    ProtonAccountProfile,
    get_profile,
    list_profiles,
    merge_overrides,
    profile_to_overrides,
    save_profile,
)
from mailops.cli.runtime import build_runtime
from mailops.core.exceptions import AdapterError

SUPPORTED_PROVIDERS = {
    "proton": "proton_bridge",
    "proton_bridge": "proton_bridge",
    "gmail": "gmail_api",
    "gmail_api": "gmail_api",
}


def connect_command(
    provider: str = typer.Argument(None, help="Provider to connect."),
    profile: str = typer.Option(None, "--profile", help="Saved Proton profile to load."),
    save_profile_name: str = typer.Option(None, "--save-profile", help="Save non-secret Proton settings under a profile name."),
    list_saved_profiles: bool = typer.Option(False, "--list-profiles", help="List saved Proton profiles."),
    host: str = typer.Option(None, "--host", help="Explicit Proton Bridge host override."),
    imap_port: int = typer.Option(None, "--imap-port", help="Explicit Proton Bridge IMAP port override."),
    smtp_port: int = typer.Option(None, "--smtp-port", help="Explicit Proton Bridge SMTP port override."),
    imap_security: str = typer.Option(None, "--imap-security", help="IMAP security mode: plain or ssl."),
    username: str = typer.Option(None, "--username", help="Explicit Proton Bridge username override."),
    password: str = typer.Option(None, "--password", help="Explicit Proton Bridge password override."),
    account_email: str = typer.Option(None, "--account-email", help="Account email if different from the username."),
    canonical_email: str = typer.Option(None, "--canonical-email", help="Canonical mailbox identity for alias consolidation."),
    config_path: str = typer.Option(None, "--config-path", help="Optional Proton config file path."),
    list_folders: bool = typer.Option(False, "--list-folders", help="Attempt to list Proton Bridge folders."),
) -> None:
    """Inspect provider connection state and optionally verify Proton Bridge access."""

    runtime = build_runtime()
    if provider is None:
        table = Table(title="Supported Providers")
        table.add_column("Alias")
        table.add_column("Adapter")
        table.add_row("proton", "proton_bridge")
        table.add_row("gmail", "gmail_api")
        runtime.console.print(table)
        runtime.console.print("Use `mailops connect proton --list-folders` to verify a Bridge-backed account.")
        return

    normalized = SUPPORTED_PROVIDERS.get(provider.strip().lower())
    if normalized is None:
        raise typer.BadParameter("supported providers: proton, proton_bridge, gmail, gmail_api")

    if normalized == "gmail_api":
        runtime.console.print("Gmail connection flow remains a placeholder in the current milestone.")
        return

    if list_saved_profiles:
        profiles = list_profiles(runtime.config)
        table = Table(title="Saved Proton Profiles")
        table.add_column("Profile")
        table.add_column("Username")
        table.add_column("Account Email")
        table.add_column("Canonical Email")
        if not profiles:
            table.add_row("(none)", "-", "-", "-")
        else:
            for saved in profiles:
                table.add_row(
                    saved.profile_name,
                    saved.username,
                    saved.account_email,
                    saved.canonical_email or saved.account_email,
                )
        runtime.console.print(table)
        return

    profile_overrides = None
    if profile is not None:
        saved_profile = get_profile(runtime.config, profile)
        if saved_profile is None:
            runtime.console.print(f"Saved Proton profile '{profile}' was not found.")
            return
        profile_overrides = profile_to_overrides(saved_profile)

    explicit_overrides = BridgeDiscoveryOverrides(
        profile_name=profile,
        host=host,
        imap_port=imap_port,
        smtp_port=smtp_port,
        imap_security=imap_security,
        username=username,
        password=password,
        account_email=account_email,
        canonical_email=canonical_email,
        config_path=config_path,
    )
    overrides = merge_overrides(profile_overrides, explicit_overrides)
    adapter = ProtonBridgeAdapter(runtime.config)
    endpoint = adapter.discover(overrides=overrides)

    table = Table(title="Proton Bridge Discovery")
    table.add_column("Field")
    table.add_column("Value")
    for key, value in endpoint.redacted_summary().items():
        table.add_row(key, value)
    runtime.console.print(table)

    if save_profile_name is not None:
        if not endpoint.username:
            runtime.console.print("Unable to save Proton profile because the Bridge username is not resolved.")
            return
        profile_record = ProtonAccountProfile(
            profile_name=save_profile_name,
            host=endpoint.host,
            imap_port=endpoint.imap_port,
            smtp_port=endpoint.smtp_port,
            imap_security=endpoint.imap_security,
            username=endpoint.username or "",
            account_email=endpoint.account_email or endpoint.username or "",
            canonical_email=endpoint.canonical_email,
        )
        save_profile(runtime.config, profile_record)
        runtime.console.print(
            f"Saved Proton profile '{save_profile_name}'. Passwords are not persisted; use env vars or --password when syncing."
        )

    if not list_folders:
        runtime.console.print("Bridge discovery is ready. Add `--list-folders` to verify IMAP access.")
        return

    try:
        folders = adapter.list_folders(overrides=overrides)
    except AdapterError as exc:
        runtime.console.print(f"Unable to list folders: {exc}")
        return

    folder_table = Table(title="Proton Bridge Folders")
    folder_table.add_column("Folder")
    folder_table.add_column("Role")
    folder_table.add_column("Delimiter")
    folder_table.add_column("Selectable")
    folder_table.add_column("Sync")
    folder_table.add_column("Draft Target")
    folder_table.add_column("Attributes")
    for folder_record in folders:
        folder_table.add_row(
            folder_record.name,
            folder_record.role,
            folder_record.delimiter,
            str(folder_record.is_selectable).lower(),
            str(folder_record.can_sync).lower(),
            str(folder_record.can_create_draft).lower(),
            ", ".join(folder_record.attributes),
        )
    runtime.console.print(folder_table)
