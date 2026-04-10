"""Implementation of `mailops export`."""

from pathlib import Path

import typer

from rich.markdown import Markdown

from mailops.cli.runtime import build_runtime
from mailops.index.db import get_table_counts
from mailops.review.batches import get_review_batch, list_audit_events, list_review_batches

export_app = typer.Typer(
    help="Export local MailOps artifacts.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@export_app.callback()
def export_callback(ctx: typer.Context) -> None:
    """Show available export surfaces when invoked without a subcommand."""

    if ctx.invoked_subcommand is not None:
        return
    runtime = build_runtime()
    runtime.console.print("Available exports: audit")


def _build_markdown_report() -> str:
    runtime = build_runtime()
    counts = get_table_counts(runtime.config)
    batches = list_review_batches(runtime.config)
    audit_events = list_audit_events(runtime.config, limit=20)
    lines = [
        "# MailOps Audit Export",
        "",
        "## Local State",
        "",
        f"- Environment: `{runtime.config.environment}`",
        f"- Database: `{runtime.config.db_path}`",
        f"- Accounts indexed: `{counts['accounts']}`",
        f"- Threads indexed: `{counts['threads']}`",
        f"- Messages indexed: `{counts['messages']}`",
        f"- Draft proposals: `{counts['draft_proposals']}`",
        f"- Action proposals: `{counts['action_proposals']}`",
        f"- Provider draft snapshots: `{counts['provider_drafts']}`",
        f"- Review batches: `{counts['review_batches']}`",
        "",
        "## Review Batches",
        "",
    ]
    if not batches:
        lines.append("- No review batches recorded.")
    else:
        for batch in batches:
            lines.append(
                f"- `{batch.batch_id}`: type=`{batch.batch_type}`, status=`{batch.status}`, risk=`{batch.highest_risk.value}`, created_at=`{batch.created_at.isoformat()}`"
            )
    lines.extend(["", "## Provider Drafts", ""])
    provider_drafts = []
    for batch in batches:
        detail = get_review_batch(runtime.config, batch.batch_id)
        if detail is not None:
            provider_drafts.extend(detail.provider_drafts)
    if not provider_drafts:
        lines.append("- No provider draft snapshots recorded.")
    else:
        for draft in provider_drafts:
            uid = draft.uid if draft.uid is not None else "-"
            lines.append(
                f"- action=`{draft.action_id}` status=`{draft.status}` mailbox=`{draft.mailbox}` uid=`{uid}` subject=`{draft.subject}` synced_at=`{draft.synced_at.isoformat()}`"
            )
    lines.extend(["", "## Audit Events", ""])
    if not audit_events:
        lines.append("- No audit events recorded.")
    else:
        for event in audit_events:
            lines.append(
                f"- `{event.timestamp.isoformat()}` `{event.action_type}` target=`{event.target_ref}` actor=`{event.actor}` result=`{event.result}`"
            )
    return "\n".join(lines)


@export_app.command("audit")
def export_audit_command(
    format: str = typer.Option("markdown", "--format", help="Export format."),
    output: str = typer.Option("-", "--output", help="Output path or '-' for stdout."),
) -> None:
    """Export a minimal local audit report."""

    runtime = build_runtime()
    if format != "markdown":
        raise typer.BadParameter("only markdown export is supported in the current milestone")

    report = _build_markdown_report()
    if output == "-":
        runtime.console.print(Markdown(report))
        return

    output_path = Path(output)
    output_path.write_text(report, encoding="utf-8")
    runtime.console.print(f"Wrote audit export to {output_path}")
