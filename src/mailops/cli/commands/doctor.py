"""Implementation of `mailops doctor`."""

from rich.table import Table

from mailops.adapters.proton_bridge.bridge_discovery import discover_bridge
from mailops.adapters.proton_bridge.networking import (
    bridge_host_candidates,
    is_wsl_environment,
    probe_tcp_endpoint,
)
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
    for host in bridge_hosts:
        imap = probe_tcp_endpoint(host, proton_endpoint.imap_port)
        smtp = probe_tcp_endpoint(host, proton_endpoint.smtp_port)
        table.add_row(
            f"proton_imap:{host}",
            "ok" if imap.reachable else "warn",
            "reachable" if imap.reachable else imap.error or "not reachable",
        )
        table.add_row(
            f"proton_smtp:{host}",
            "ok" if smtp.reachable else "warn",
            "reachable" if smtp.reachable else smtp.error or "not reachable",
        )

    runtime.console.print(table)
