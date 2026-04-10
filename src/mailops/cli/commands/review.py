"""Implementation of `mailops review`."""

import typer

from rich.table import Table

from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.cli.runtime import build_runtime
from mailops.review.batches import get_review_batch, list_review_batches
from mailops.review.provider_drafts import sync_review_batch_provider_drafts
from mailops.utils.text import safe_console_text

review_app = typer.Typer(
    help="Inspect pending review work.",
    invoke_without_command=True,
    no_args_is_help=False,
)
batch_app = typer.Typer(
    help="Inspect review batches.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@review_app.callback()
def review_callback(ctx: typer.Context) -> None:
    """Show review queue status when invoked without a subcommand."""

    if ctx.invoked_subcommand is not None:
        return
    runtime = build_runtime()
    batches = list_review_batches(runtime.config)
    pending_batches = [batch for batch in batches if batch.status == "pending"]
    runtime.console.print(f"Pending review batches: {len(pending_batches)}")
    if batches:
        runtime.console.print("Use `mailops review batch list` or `mailops review batch show <id>` for details.")
    else:
        runtime.console.print("No review work is queued.")


@batch_app.callback()
def batch_callback(ctx: typer.Context) -> None:
    """Show help text for review batch operations."""

    if ctx.invoked_subcommand is not None:
        return
    runtime = build_runtime()
    runtime.console.print("Review batch commands inspect proposed action batches.")


@batch_app.command("list")
def batch_list_command() -> None:
    """List review batches."""

    runtime = build_runtime()
    batches = list_review_batches(runtime.config)
    table = Table(title="Review Batches")
    table.add_column("Batch ID")
    table.add_column("Type")
    table.add_column("Risk")
    table.add_column("Status")
    table.add_column("Created")

    if not batches:
        table.add_row("(none)", "-", "-", "empty", "-")
    else:
        for batch in batches:
            table.add_row(
                batch.batch_id,
                batch.batch_type,
                batch.highest_risk.value,
                batch.status,
                batch.created_at.isoformat(),
            )

    runtime.console.print(table)


@batch_app.command("show")
def batch_show_command(batch_id: str = typer.Argument(..., help="Review batch identifier.")) -> None:
    """Show a single review batch."""

    runtime = build_runtime()
    batch = get_review_batch(runtime.config, batch_id)
    if batch is None:
        runtime.console.print(f"Batch '{batch_id}' was not found in local state.")
        return

    table = Table(title=f"Review Batch {batch.batch_id}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("type", batch.batch_type)
    table.add_row("status", batch.status)
    table.add_row("scope_count", str(batch.scope_count))
    table.add_row("highest_risk", batch.highest_risk.value)
    table.add_row("reason", batch.reason)
    table.add_row("rollback_available", str(batch.rollback_available).lower())
    table.add_row("created_at", batch.created_at.isoformat())
    runtime.console.print(table)

    action_table = Table(title="Actions")
    action_table.add_column("Action ID")
    action_table.add_column("Type")
    action_table.add_column("Review")
    action_table.add_column("Execution")
    action_table.add_column("Draft Ref")
    action_table.add_column("Provider Ref")
    if not batch.actions:
        action_table.add_row("(none)", "-", "-", "-", "-", "-")
    else:
        for action in batch.actions:
            action_table.add_row(
                action.id,
                action.type,
                action.review_status.value,
                action.execution_status.value,
                action.draft_proposal_id or "-",
                action.provider_ref or "-",
            )
    runtime.console.print(action_table)

    draft_table = Table(title="Draft Proposals")
    draft_table.add_column("Draft ID")
    draft_table.add_column("Style")
    draft_table.add_column("Account")
    draft_table.add_column("To")
    draft_table.add_column("Subject")
    draft_table.add_column("Confidence")
    if not batch.draft_proposals:
        draft_table.add_row("(none)", "-", "-", "-", "-", "-")
    else:
        for draft in batch.draft_proposals:
            draft_table.add_row(
                draft.id,
                draft.style_profile,
                draft.account_id or "-",
                safe_console_text(", ".join(draft.to_recipients) or "-", runtime.console),
                safe_console_text(draft.proposed_subject, runtime.console),
                f"{draft.confidence:.0%}",
            )
    runtime.console.print(draft_table)

    if batch.draft_proposals:
        runtime.console.print("Draft refs:")
        for draft in batch.draft_proposals:
            runtime.console.print(
                " - "
                f"draft_id={safe_console_text(draft.id, runtime.console)} "
                f"account={safe_console_text(draft.account_id or '-', runtime.console)} "
                f"to={safe_console_text(', '.join(draft.to_recipients) or '-', runtime.console)} "
                f"subject={safe_console_text(draft.proposed_subject, runtime.console)}"
            )
        body_table = Table(title="Draft Bodies")
        body_table.add_column("Draft ID")
        body_table.add_column("Context Refs")
        body_table.add_column("Body")
        for draft in batch.draft_proposals:
            body_table.add_row(
                draft.id,
                safe_console_text(", ".join(draft.context_refs) or "-", runtime.console),
                safe_console_text(draft.proposed_body, runtime.console),
            )
        runtime.console.print(body_table)

    provider_draft_table = Table(title="Provider Draft Snapshots")
    provider_draft_table.add_column("Action ID")
    provider_draft_table.add_column("Status")
    provider_draft_table.add_column("Mailbox")
    provider_draft_table.add_column("UID")
    provider_draft_table.add_column("Subject")
    provider_draft_table.add_column("Synced")
    if not batch.provider_drafts:
        provider_draft_table.add_row("(none)", "-", "-", "-", "-", "-")
    else:
        for draft in batch.provider_drafts:
            provider_draft_table.add_row(
                draft.action_id,
                draft.status,
                draft.mailbox,
                str(draft.uid) if draft.uid is not None else "-",
                safe_console_text(draft.subject, runtime.console),
                draft.synced_at.isoformat(),
            )
    runtime.console.print(provider_draft_table)


@batch_app.command("sync-drafts")
def batch_sync_drafts_command(
    batch_id: str = typer.Argument(..., help="Review batch identifier."),
    host: str = typer.Option(None, "--host", help="Explicit Proton Bridge host override."),
    imap_port: int = typer.Option(None, "--imap-port", help="Explicit Proton Bridge IMAP port override."),
    imap_security: str = typer.Option(None, "--imap-security", help="IMAP security mode: plain or ssl."),
    password: str = typer.Option(None, "--password", help="Transient Proton Bridge password override."),
    config_path: str = typer.Option(None, "--config-path", help="Optional Proton config file path."),
) -> None:
    """Sync provider metadata for drafts created by an executed review batch."""

    runtime = build_runtime()
    result = sync_review_batch_provider_drafts(
        runtime.config,
        batch_id,
        actor="mailops.review",
        proton_overrides=BridgeDiscoveryOverrides(
            host=host,
            imap_port=imap_port,
            imap_security=imap_security,
            password=password,
            config_path=config_path,
        ),
    )
    if result is None:
        runtime.console.print(f"Batch '{batch_id}' was not found. Nothing was synced.")
        return
    runtime.console.print(
        f"Synced provider draft metadata for batch '{batch_id}': "
        f"present={result.synced_drafts}, missing={result.missing_drafts}, failed={result.failed_drafts}."
    )
    for error in result.errors:
        runtime.console.print(f"Sync note: {error}")


review_app.add_typer(batch_app, name="batch")
