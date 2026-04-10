"""Implementation of `mailops search`."""

import typer

from rich.table import Table

from mailops.cli.runtime import build_runtime
from mailops.index.search import SearchRequest, search_messages
from mailops.utils.text import safe_console_text


def search_command(
    query: str = typer.Argument("", help="Search text."),
    account: str = typer.Option(None, "--account", help="Restrict to an account id."),
    limit: int = typer.Option(20, "--limit", min=1, max=200, help="Maximum results."),
) -> None:
    """Search synced local mailbox state."""

    runtime = build_runtime()
    request = SearchRequest(query=query, account_id=account, limit=limit)
    results = search_messages(runtime.config, request)

    table = Table(title="Search")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("query", query or "(empty)")
    table.add_row("account", account or "all")
    table.add_row("results", str(len(results)))
    runtime.console.print(table)

    if not results:
        runtime.console.print("No indexed results yet. Run `mailops sync` against a Proton Bridge account first.")
        return

    result_table = Table(title="Matches")
    result_table.add_column("Thread ID")
    result_table.add_column("Message ID")
    result_table.add_column("Account")
    result_table.add_column("Sender")
    result_table.add_column("Subject")
    result_table.add_column("When")
    result_table.add_column("Snippet")
    for row in results:
        result_table.add_row(
            safe_console_text(row["thread_id"], runtime.console),
            safe_console_text(row["message_id"], runtime.console),
            safe_console_text(row["account_id"], runtime.console),
            safe_console_text(row["sender"], runtime.console),
            safe_console_text(row["subject"], runtime.console),
            safe_console_text(row["sort_time"], runtime.console),
            safe_console_text(row["snippet"], runtime.console),
        )
    runtime.console.print(result_table)
    runtime.console.print("Inspect refs:")
    for row in results:
        runtime.console.print(
            " - "
            f"thread_id={safe_console_text(row['thread_id'], runtime.console)} "
            f"message_id={safe_console_text(row['message_id'], runtime.console)}"
        )
