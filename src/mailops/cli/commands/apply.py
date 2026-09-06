"""Implementation of `mailops apply`."""

import typer

from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.cli.runtime import build_runtime
from mailops.review.batches import get_review_batch
from mailops.review.execution import execute_review_batch


def apply_command(
    batch_id: str = typer.Argument(None, help="Review batch identifier."),
    host: str = typer.Option(None, "--host", help="Explicit Proton Bridge host override."),
    imap_port: int = typer.Option(None, "--imap-port", help="Explicit Proton Bridge IMAP port override."),
    imap_security: str = typer.Option(None, "--imap-security", help="IMAP security mode: plain or ssl."),
    password: str = typer.Option(None, "--password", help="Transient Proton Bridge password override."),
    config_path: str = typer.Option(None, "--config-path", help="Optional Proton config file path."),
) -> None:
    """Apply a review batch and materialize provider-side drafts when possible."""

    runtime = build_runtime()
    if batch_id is None:
        runtime.console.print("Provide a batch id to apply. High-risk actions remain blocked by default.")
        raise typer.Exit(1)

    batch = get_review_batch(runtime.config, batch_id)
    if batch is None:
        runtime.console.print(f"Batch '{batch_id}' was not found. Nothing was applied.")
        raise typer.Exit(1)

    result = execute_review_batch(
        runtime.config,
        batch_id,
        actor="mailops.apply",
        proton_overrides=BridgeDiscoveryOverrides(
            host=host,
            imap_port=imap_port,
            imap_security=imap_security,
            password=password,
            config_path=config_path,
        ),
    )
    if result is None:
        runtime.console.print(f"Batch '{batch_id}' was not found. Nothing was applied.")
        raise typer.Exit(1)
    approved = get_review_batch(runtime.config, batch_id)
    if approved is None:
        runtime.console.print(f"Batch '{batch_id}' was not found after execution. Nothing was applied.")
        raise typer.Exit(1)
    if approved.highest_risk.value == "high":
        runtime.console.print(f"Batch '{batch_id}' remains blocked because it contains high-risk actions.")
        raise typer.Exit(1)
    if approved.status == "rolled_back":
        runtime.console.print(f"Batch '{batch_id}' was already rolled back and cannot be applied.")
        raise typer.Exit(1)

    if result.uncertain_actions:
        runtime.console.print(
            f"Batch '{batch_id}' needs attention for {result.uncertain_actions} action(s). "
            "A provider draft may already exist. Inspect Proton Drafts before recovery; "
            "automatic retry and local rollback are blocked."
        )
    elif result.executed_actions:
        runtime.console.print(
            f"Applied batch '{batch_id}'. Materialized {result.executed_actions} provider draft(s); batch status is '{result.batch_status}'."
        )
    elif result.batch_status == "executed" and result.pending_actions == 0 and result.failed_actions == 0:
        runtime.console.print(f"Batch '{batch_id}' was already applied; provider-side drafts are already present.")
    elif result.failed_actions and result.pending_actions == 0:
        runtime.console.print(
            f"Approved batch '{batch_id}' locally, but provider execution failed for {result.failed_actions} action(s)."
        )
    else:
        runtime.console.print(
            f"Approved batch '{batch_id}' locally. Provider-side execution is still pending for {result.pending_actions} action(s)."
        )
    for error in result.errors:
        runtime.console.print(f"Execution note: {error}")
    if result.failed_actions or result.uncertain_actions:
        raise typer.Exit(1)
