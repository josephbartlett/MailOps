"""Implementation of `mailops sync`."""

from dataclasses import dataclass

import typer
from typing import List, Optional

from rich.table import Table

from mailops.adapters.proton_bridge.adapter import ProtonBridgeAdapter
from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.adapters.proton_bridge.imap_sync import ImapSyncRequest
from mailops.adapters.proton_bridge.registry import (
    find_matching_profiles,
    get_profile,
    list_profiles,
    merge_overrides,
    profile_to_overrides,
)
from mailops.cli.runtime import build_runtime
from mailops.core.exceptions import AdapterError
from mailops.core.models import SyncResult


@dataclass(frozen=True)
class ProtonSyncTarget:
    label: str
    request_account_id: str | None
    overrides: BridgeDiscoveryOverrides


def _identity_overrides_requested(overrides: BridgeDiscoveryOverrides) -> bool:
    return any(
        (
            overrides.username,
            overrides.account_email,
            overrides.canonical_email,
        )
    )


def _global_overrides(overrides: BridgeDiscoveryOverrides) -> BridgeDiscoveryOverrides:
    return BridgeDiscoveryOverrides(
        host=overrides.host,
        imap_port=overrides.imap_port,
        smtp_port=overrides.smtp_port,
        imap_security=overrides.imap_security,
        password=overrides.password,
        config_path=overrides.config_path,
    )


def _resolve_sync_targets(
    *,
    profile: str | None,
    account: str,
    explicit_overrides: BridgeDiscoveryOverrides,
    adapter: ProtonBridgeAdapter,
) -> list[ProtonSyncTarget]:
    matched_profiles = []
    if profile is not None and profile.strip().lower() != "all":
        saved_profile = get_profile(adapter.config, profile)
        if saved_profile is None:
            raise typer.BadParameter(f"saved Proton profile '{profile}' was not found")
        return [
            ProtonSyncTarget(
                label=saved_profile.profile_name,
                request_account_id=None,
                overrides=merge_overrides(profile_to_overrides(saved_profile), explicit_overrides),
            )
        ]

    saved_profiles = list_profiles(adapter.config)
    if profile is not None and profile.strip().lower() == "all":
        matched_profiles = saved_profiles
        if not matched_profiles:
            raise typer.BadParameter("no saved Proton profiles were found")
    elif account != "all":
        matched_profiles = find_matching_profiles(adapter.config, account)
    elif saved_profiles and not (explicit_overrides.username or explicit_overrides.account_email):
        matched_profiles = saved_profiles

    if matched_profiles:
        if len(matched_profiles) > 1 and _identity_overrides_requested(explicit_overrides):
            raise typer.BadParameter(
                "cannot combine multi-profile Proton sync with explicit --username, --account-email, or --canonical-email"
            )

        targets: list[ProtonSyncTarget] = []
        shared_explicit_overrides = _global_overrides(explicit_overrides) if len(matched_profiles) > 1 else explicit_overrides
        for saved_profile in matched_profiles:
            targets.append(
                ProtonSyncTarget(
                    label=saved_profile.profile_name,
                    request_account_id=None,
                    overrides=merge_overrides(profile_to_overrides(saved_profile), shared_explicit_overrides),
                )
            )
        return targets

    if explicit_overrides.username or explicit_overrides.account_email:
        return [
            ProtonSyncTarget(
                label=explicit_overrides.profile_name or explicit_overrides.account_email or explicit_overrides.username or "proton",
                request_account_id=None if account == "all" else account,
                overrides=explicit_overrides,
            )
        ]

    return [
        ProtonSyncTarget(
            label=account if account != "all" else "proton",
            request_account_id=None if account == "all" else account,
            overrides=explicit_overrides,
        )
    ]


def _print_sync_result(runtime: object, *, provider: str, target: ProtonSyncTarget, result: SyncResult) -> None:
    table = Table(title="Sync Result")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("provider", provider)
    table.add_row("target", target.label)
    table.add_row("account", result.account_id)
    table.add_row("folders_discovered", ", ".join(result.folders_discovered) or "(none)")
    table.add_row("folders_synced", ", ".join(result.folders_synced) or "(none)")
    table.add_row("messages_indexed", str(result.messages_indexed))
    table.add_row("warnings", str(len(result.warnings)))
    table.add_row("errors", str(len(result.errors)))
    runtime.console.print(table)


def _print_multi_sync_results(runtime: object, *, provider: str, results: list[tuple[ProtonSyncTarget, SyncResult]]) -> None:
    table = Table(title="Sync Results")
    table.add_column("Provider")
    table.add_column("Target")
    table.add_column("Account")
    table.add_column("Folders Synced")
    table.add_column("Messages")
    table.add_column("Warnings")
    table.add_column("Errors")
    total_messages = 0
    total_warnings = 0
    total_errors = 0
    for target, result in results:
        total_messages += result.messages_indexed
        total_warnings += len(result.warnings)
        total_errors += len(result.errors)
        table.add_row(
            provider,
            target.label,
            result.account_id,
            ", ".join(result.folders_synced) or "(none)",
            str(result.messages_indexed),
            str(len(result.warnings)),
            str(len(result.errors)),
        )
    runtime.console.print(table)
    runtime.console.print(
        f"Synced {len(results)} Proton target(s). Indexed {total_messages} messages, {total_warnings} warnings, {total_errors} errors."
    )


def sync_command(
    account: str = typer.Option("all", "--account", help="Account id or 'all'."),
    provider: str = typer.Option(None, "--provider", help="Provider to sync. Defaults to the configured provider."),
    profile: str = typer.Option(None, "--profile", help="Saved Proton profile to load. Use 'all' to sync every saved Proton profile."),
    folder: Optional[List[str]] = typer.Option(None, "--folder", help="Folder(s) to sync."),
    limit: int = typer.Option(250, "--limit", min=1, help="Maximum messages per sync slice."),
    host: str = typer.Option(None, "--host", help="Explicit Proton Bridge host override."),
    imap_port: int = typer.Option(None, "--imap-port", help="Explicit Proton Bridge IMAP port override."),
    smtp_port: int = typer.Option(None, "--smtp-port", help="Explicit Proton Bridge SMTP port override."),
    imap_security: str = typer.Option(None, "--imap-security", help="IMAP security mode: plain or ssl."),
    username: str = typer.Option(None, "--username", help="Explicit Proton Bridge username override."),
    password: str = typer.Option(None, "--password", help="Explicit Proton Bridge password override."),
    account_email: str = typer.Option(None, "--account-email", help="Account email if different from the username."),
    canonical_email: str = typer.Option(None, "--canonical-email", help="Canonical mailbox identity for alias consolidation."),
    config_path: str = typer.Option(None, "--config-path", help="Optional Proton config file path."),
) -> None:
    """Sync mailbox data for the selected provider into the local index."""

    runtime = build_runtime()
    selected_provider = (provider or runtime.config.default_provider).strip().lower()
    if selected_provider in {"gmail", "gmail_api"}:
        runtime.console.print("Gmail sync is not implemented yet.")
        raise typer.Exit(1)

    if selected_provider not in {"proton", "proton_bridge"}:
        raise typer.BadParameter("supported sync providers: proton, proton_bridge, gmail, gmail_api")

    adapter = ProtonBridgeAdapter(runtime.config)
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
    try:
        targets = _resolve_sync_targets(
            profile=profile,
            account=account,
            explicit_overrides=explicit_overrides,
            adapter=adapter,
        )
    except typer.BadParameter as exc:
        runtime.console.print(f"Sync failed: {exc}")
        raise typer.Exit(1) from exc

    results: list[tuple[ProtonSyncTarget, SyncResult]] = []
    for target in targets:
        request = ImapSyncRequest(
            account_id=target.request_account_id,
            folders=list(folder or []),
            limit=limit,
        )
        try:
            result = adapter.sync(request, overrides=target.overrides)
        except AdapterError as exc:
            runtime.console.print(f"Sync failed for '{target.label}': {exc}")
            raise typer.Exit(1) from exc
        results.append((target, result))

    if len(results) == 1:
        target, result = results[0]
        _print_sync_result(runtime, provider=selected_provider, target=target, result=result)
    else:
        _print_multi_sync_results(runtime, provider=selected_provider, results=results)

    for target, result in results:
        for warning in result.warnings:
            runtime.console.print(f"[{target.label}] Warning: {warning}")
        for error in result.errors:
            runtime.console.print(f"[{target.label}] Error: {error}")
    if any(result.errors for _, result in results):
        raise typer.Exit(1)
