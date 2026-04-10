"""Implementation of `mailops doctor`."""

from rich.table import Table

from mailops.adapters.proton_bridge.bridge_discovery import discover_bridge
from mailops.adapters.proton_bridge.networking import (
    bridge_host_candidates,
    is_wsl_environment,
    probe_tcp_endpoint,
)
from mailops.adapters.proton_bridge.registry import list_profiles, profile_to_overrides
from mailops.cli.runtime import build_runtime
from mailops.index.db import get_table_counts, list_tables


def doctor_command() -> None:
    """Validate the local MailOps runtime and print a concise report."""

    runtime = build_runtime()
    counts = get_table_counts(runtime.config)
    tables = ", ".join(list_tables(runtime.config))

    table = Table(title="MailOps Doctor", show_lines=True)
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    table.add_row("home_dir", "ok", str(runtime.config.home_dir))
    table.add_row("db_path", "ok", str(runtime.config.db_path))
    table.add_row("log_path", "ok", str(runtime.config.log_path))
    table.add_row("tables", "ok", tables)
    table.add_row("records", "ok", ", ".join(f"{name}={count}" for name, count in counts.items()))

    wsl_detected = is_wsl_environment()
    table.add_row("wsl", "info", "detected" if wsl_detected else "not detected")

    proton_endpoint = discover_bridge(runtime.config)
    bridge_hosts = bridge_host_candidates(proton_endpoint.host)
    table.add_row("proton_bridge_hosts", "info", ", ".join(bridge_hosts))
    _add_bridge_probe_rows(
        table,
        label="default",
        hosts=bridge_hosts,
        imap_port=proton_endpoint.imap_port,
        smtp_port=proton_endpoint.smtp_port,
    )

    profiles = list_profiles(runtime.config)
    table.add_row("proton_profiles", "info", ", ".join(profile.profile_name for profile in profiles) or "(none)")
    for profile in profiles:
        endpoint = discover_bridge(runtime.config, overrides=profile_to_overrides(profile))
        profile_hosts = bridge_host_candidates(endpoint.host)
        table.add_row(
            f"proton_profile:{profile.profile_name}",
            "info",
            f"hosts={', '.join(profile_hosts)} imap={endpoint.imap_port} smtp={endpoint.smtp_port}",
        )
        _add_bridge_probe_rows(
            table,
            label=profile.profile_name,
            hosts=profile_hosts,
            imap_port=endpoint.imap_port,
            smtp_port=endpoint.smtp_port,
        )

    runtime.console.print(table)


def _add_bridge_probe_rows(table: Table, *, label: str, hosts: list[str], imap_port: int, smtp_port: int) -> None:
    for host in hosts:
        imap = probe_tcp_endpoint(host, imap_port)
        smtp = probe_tcp_endpoint(host, smtp_port)
        table.add_row(
            f"proton_imap:{label}:{host}:{imap_port}",
            "ok" if imap.reachable else "warn",
            "reachable" if imap.reachable else imap.error or "not reachable",
        )
        table.add_row(
            f"proton_smtp:{label}:{host}:{smtp_port}",
            "ok" if smtp.reachable else "warn",
            "reachable" if smtp.reachable else smtp.error or "not reachable",
        )
