"""Implementation of `mailops status`."""

from rich.table import Table

from mailops.cli.runtime import build_runtime
from mailops.index.db import get_pending_action_proposal_count, get_table_counts


def status_command() -> None:
    """Show the current local MailOps state."""

    runtime = build_runtime()
    counts = get_table_counts(runtime.config)
    pending_action_count = get_pending_action_proposal_count(runtime.config)

    table = Table(title="MailOps Status")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("environment", runtime.config.environment)
    table.add_row("default_provider", runtime.config.default_provider)
    table.add_row("model_provider", runtime.config.model_provider)
    table.add_row("redact_logs", str(runtime.config.redact_logs).lower())
    table.add_row("accounts", str(counts["accounts"]))
    table.add_row("account_aliases", str(counts["account_aliases"]))
    table.add_row("folders", str(counts["folders"]))
    table.add_row("threads", str(counts["threads"]))
    table.add_row("messages", str(counts["messages"]))
    table.add_row("folder_links", str(counts["folder_messages"]))
    table.add_row("provider_drafts", str(counts["provider_drafts"]))
    table.add_row("review_batches", str(counts["review_batches"]))
    table.add_row("pending_action_proposals", str(pending_action_count))
    runtime.console.print(table)
