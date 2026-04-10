"""Implementation of `mailops draft`."""

from __future__ import annotations

from pathlib import Path

import typer

from mailops.cli.runtime import build_runtime
from mailops.core.models import ProviderName
from mailops.review.custom_drafts import CustomDraftRequest, create_custom_draft_review_batch

draft_app = typer.Typer(
    help="Create review-first draft proposals.",
    no_args_is_help=True,
)


@draft_app.command("create")
def draft_create_command(
    to: list[str] = typer.Option(..., "--to", help="Recipient email address. Repeat for multiple recipients."),
    subject: str = typer.Option(..., "--subject", help="Draft subject."),
    body: str | None = typer.Option(None, "--body", help="Draft body text."),
    body_file: Path | None = typer.Option(
        None,
        "--body-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a UTF-8 text file containing the draft body.",
    ),
    from_account: str | None = typer.Option(
        None,
        "--from-account",
        help="MailOps account id or email address to draft from. Required when multiple provider accounts exist.",
    ),
    cc: list[str] = typer.Option([], "--cc", help="CC recipient. Repeat for multiple recipients."),
    bcc: list[str] = typer.Option([], "--bcc", help="BCC recipient. Repeat for multiple recipients."),
    context_ref: list[str] = typer.Option(
        [],
        "--context-ref",
        help="Context reference such as a repo path, issue id, thread id, or message id. Repeat as needed.",
    ),
    provider: ProviderName = typer.Option(
        ProviderName.PROTON_BRIDGE,
        "--provider",
        help="Provider used for draft materialization.",
    ),
) -> None:
    """Create a pending review batch for a custom outbound draft."""

    runtime = build_runtime()
    if body is not None and body_file is not None:
        runtime.console.print("Use either --body or --body-file, not both.")
        return
    if body_file is not None:
        body_text = body_file.read_text(encoding="utf-8")
    else:
        body_text = body or ""

    try:
        result = create_custom_draft_review_batch(
            runtime.config,
            CustomDraftRequest(
                provider=provider,
                account_id=from_account,
                to_recipients=to,
                cc_recipients=cc,
                bcc_recipients=bcc,
                subject=subject,
                body_text=body_text,
                context_refs=context_ref,
            ),
        )
    except ValueError as exc:
        runtime.console.print(str(exc))
        return

    runtime.console.print(
        f"Created review batch `{result.batch_id}` with custom draft `{result.draft_id}` "
        f"from `{result.account_id}` to {', '.join(result.to_recipients)}."
    )
    runtime.console.print(f"Inspect it with `mailops review batch show {result.batch_id}`.")
