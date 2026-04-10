"""Implementation of `mailops triage`."""

import typer

from rich.table import Table

from mailops.cli.runtime import build_runtime
from mailops.index.triage import list_triage_threads, refresh_thread_triage, summarize_followup_states
from mailops.utils.dates import parse_relative_days
from mailops.utils.text import safe_console_text


def triage_command(
    since: str = typer.Option("3d", "--since", help="Relative lookback window such as 3d."),
    account: str = typer.Option("all", "--account", help="Account id or 'all'."),
) -> None:
    """Show threads likely waiting on the operator."""

    runtime = build_runtime()
    older_than_days = parse_relative_days(since)
    refresh_thread_triage(runtime.config, account_id=account)
    summary = summarize_followup_states(runtime.config, account_id=account)
    threads = list_triage_threads(
        runtime.config,
        older_than_days=older_than_days,
        account_id=account,
        states=("waiting_on_me",),
        limit=20,
    )

    table = Table(title="Triage")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("account", account)
    table.add_row("window", since)
    table.add_row("waiting_on_me", str(summary["waiting_on_me"]))
    table.add_row("waiting_on_them", str(summary["waiting_on_them"]))
    table.add_row("resolved", str(summary["resolved"]))
    table.add_row("ambiguous", str(summary["ambiguous"]))
    table.add_row("ranked_results", str(len(threads)))
    runtime.console.print(table)

    if not threads:
        runtime.console.print("No waiting-on-me threads matched the current window.")
        return

    result_table = Table(title="Waiting On Me")
    result_table.add_column("Account")
    result_table.add_column("Subject")
    result_table.add_column("Score")
    result_table.add_column("Last Message")
    result_table.add_column("Unread")
    result_table.add_column("Reasons")
    for row in threads:
        result_table.add_row(
            safe_console_text(row["account_id"], runtime.console),
            safe_console_text(row["subject"], runtime.console),
            safe_console_text(f"{float(row['importance_score']):.0%}", runtime.console),
            safe_console_text(row["last_message_at"], runtime.console),
            safe_console_text(str(row["unread_count"]), runtime.console),
            safe_console_text(", ".join(row["classification_tags"][:3]), runtime.console),
        )
    runtime.console.print(result_table)
