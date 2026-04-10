"""Local demo dataset commands."""

from __future__ import annotations

import typer

from mailops.cli.runtime import build_runtime
from mailops.demo.seed import seed_demo_mailbox

demo_app = typer.Typer(
    help="Seed local-only demo data.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@demo_app.callback()
def demo_callback(ctx: typer.Context) -> None:
    """Show demo command guidance."""

    if ctx.invoked_subcommand is not None:
        return
    runtime = build_runtime()
    runtime.console.print("Available demo command: `mailops demo seed`.")


@demo_app.command("seed")
def demo_seed_command() -> None:
    """Create or refresh the local demo mailbox fixture."""

    runtime = build_runtime()
    result = seed_demo_mailbox(runtime.config)
    runtime.console.print(
        f"Seeded local demo mailbox '{result.account_id}' with {result.threads} threads and {result.messages} messages."
    )
