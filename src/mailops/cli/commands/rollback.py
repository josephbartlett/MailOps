"""Implementation of `mailops rollback`."""

import typer

from mailops.cli.runtime import build_runtime
from mailops.review.batches import get_review_batch, rollback_review_batch


def rollback_command(batch_id: str = typer.Argument(None, help="Review batch identifier.")) -> None:
    """Describe rollback behavior without faking reversible provider state."""

    runtime = build_runtime()
    if batch_id is None:
        runtime.console.print("Provide a batch id to roll back.")
        return

    batch = get_review_batch(runtime.config, batch_id)
    if batch is None:
        runtime.console.print(f"Batch '{batch_id}' was not found. Nothing was rolled back.")
        return

    rolled_back = rollback_review_batch(runtime.config, batch_id, actor="mailops.rollback")
    if rolled_back is None:
        runtime.console.print(f"Batch '{batch_id}' was not found. Nothing was rolled back.")
        return
    if rolled_back.status != "rolled_back":
        runtime.console.print(
            f"Batch '{batch_id}' still has provider-side drafts or executed actions. Automatic rollback is blocked."
        )
        return
    runtime.console.print(
        f"Rolled back local artifacts for batch '{batch_id}'. Provider-side rollback is still unimplemented."
    )
