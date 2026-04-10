"""Implementation of review-only provider rule previews."""

from __future__ import annotations

import typer

from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from mailops.adapters.proton_bridge.sieve import SieveRuleProposal, generate_sieve_rule_proposal
from mailops.cli.runtime import build_runtime

rules_app = typer.Typer(
    help="Preview provider-native rules without applying them.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@rules_app.callback()
def rules_callback(ctx: typer.Context) -> None:
    """Show rule preview guidance when invoked without a subcommand."""

    if ctx.invoked_subcommand is not None:
        return
    runtime = build_runtime()
    runtime.console.print("Available rule command: `mailops rules propose <prompt>`.")
    runtime.console.print("Rule application is intentionally not implemented.")


@rules_app.command("propose")
def propose_rule_command(
    prompt: str = typer.Argument(..., help="Natural-language Proton Sieve rule request."),
    provider: str = typer.Option("proton", "--provider", help="Provider rule dialect to preview."),
) -> None:
    """Generate a review-only provider-native rule proposal."""

    runtime = build_runtime()
    if provider.strip().lower() not in {"proton", "proton_bridge"}:
        runtime.console.print("Only Proton Sieve previews are implemented in the current milestone.")
        return
    proposal = generate_sieve_rule_proposal(prompt)
    render_rule_proposal(runtime.console, proposal)


def render_rule_proposal(console: object, proposal: SieveRuleProposal) -> None:
    """Render a rule proposal consistently from `rules` and `ask`."""

    summary = Table(title="Rule Proposal")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("provider", "proton_bridge")
    summary.add_row("intent", proposal.intent)
    summary.add_row("target_mailbox", proposal.target_mailbox)
    summary.add_row("risk", "medium")
    summary.add_row("apply_supported", "false")
    console.print(summary)

    conditions = Table(title="Structured Conditions")
    conditions.add_column("Field")
    conditions.add_column("Match")
    conditions.add_column("Value")
    if not proposal.structured_conditions:
        conditions.add_row("(none)", "-", "-")
    else:
        for condition in proposal.structured_conditions:
            conditions.add_row(condition.field, condition.match_type, condition.value)
    console.print(conditions)

    console.print(Panel(proposal.explanation, title="Explanation"))
    console.print(Panel(proposal.preview, title="Preview"))
    console.print(Syntax(proposal.generated_rule_text, "sieve", theme="ansi_dark", line_numbers=False))
