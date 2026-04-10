"""Implementation of `mailops inspect`."""

from __future__ import annotations

from typing import Any

import typer

from rich.table import Table

from mailops.cli.runtime import build_runtime
from mailops.index.inspection import get_message_detail, get_thread_detail
from mailops.utils.text import safe_console_text

inspect_app = typer.Typer(
    help="Inspect local indexed email context.",
    no_args_is_help=True,
)


@inspect_app.command("thread")
def inspect_thread_command(
    thread_id: str = typer.Argument(..., help="Local MailOps thread id."),
    body_chars: int = typer.Option(1200, "--body-chars", min=0, help="Maximum body characters per message."),
) -> None:
    """Inspect a local indexed thread without contacting the provider."""

    runtime = build_runtime()
    detail = get_thread_detail(runtime.config, thread_id)
    if detail is None:
        runtime.console.print(f"Thread '{thread_id}' was not found in local state.")
        return

    thread = detail["thread"]
    messages = detail["messages"]
    thread_table = Table(title=f"Thread {thread['id']}")
    thread_table.add_column("Field")
    thread_table.add_column("Value")
    thread_table.add_row("account", _safe(thread["account_id"], runtime.console))
    thread_table.add_row("subject", _safe(thread["subject"], runtime.console))
    thread_table.add_row("last_message_at", _safe(thread["last_message_at"], runtime.console))
    thread_table.add_row("followup_state", _safe(thread["followup_state"], runtime.console))
    thread_table.add_row("importance_score", f"{float(thread['importance_score']):.0%}")
    thread_table.add_row("participants", _safe(", ".join(thread["participants"]), runtime.console))
    thread_table.add_row("classification_tags", _safe(", ".join(thread["classification_tags"]), runtime.console))
    runtime.console.print(thread_table)

    _render_messages(runtime.console, messages, body_chars=body_chars)


@inspect_app.command("message")
def inspect_message_command(
    message_id: str = typer.Argument(..., help="Local MailOps message id."),
    body_chars: int = typer.Option(2000, "--body-chars", min=0, help="Maximum body characters to print."),
) -> None:
    """Inspect a single local indexed message without contacting the provider."""

    runtime = build_runtime()
    detail = get_message_detail(runtime.config, message_id)
    if detail is None:
        runtime.console.print(f"Message '{message_id}' was not found in local state.")
        return

    thread = detail["thread"]
    message = detail["message"]
    table = Table(title=f"Message {message['id']}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("thread_id", _safe(thread["id"], runtime.console))
    table.add_row("account", _safe(thread["account_id"], runtime.console))
    table.add_row("subject", _safe(thread["subject"], runtime.console))
    table.add_row("from", _safe(message["sender"], runtime.console))
    table.add_row("to", _safe(", ".join(message["to_recipients"]), runtime.console))
    table.add_row("cc", _safe(", ".join(message["cc_recipients"]), runtime.console))
    table.add_row("when", _safe(_message_time(message), runtime.console))
    table.add_row("folders", _safe(", ".join(message["folder_or_label_refs"]), runtime.console))
    table.add_row("flags", _safe(", ".join(message["flags"]), runtime.console))
    runtime.console.print(table)

    if body_chars > 0:
        _render_body(runtime.console, message, body_chars=body_chars)


def _render_messages(console: Any, messages: list[dict[str, Any]], *, body_chars: int) -> None:
    table = Table(title="Messages")
    table.add_column("Message ID")
    table.add_column("From")
    table.add_column("To")
    table.add_column("When")
    table.add_column("Folders")
    table.add_column("Snippet")
    if not messages:
        table.add_row("(none)", "-", "-", "-", "-", "-")
    else:
        for message in messages:
            table.add_row(
                _safe(message["id"], console),
                _safe(message["sender"], console),
                _safe(", ".join(message["to_recipients"]), console),
                _safe(_message_time(message), console),
                _safe(", ".join(message["folder_or_label_refs"]), console),
                _safe(message["snippet"], console),
            )
    console.print(table)

    if body_chars <= 0:
        return
    for message in messages:
        _render_body(console, message, body_chars=body_chars)


def _render_body(console: Any, message: dict[str, Any], *, body_chars: int) -> None:
    body = str(message["body_text"])
    if not body.strip():
        console.print(f"Message {message['id']} has no indexed body text.")
        return
    preview = body[:body_chars]
    suffix = "" if len(body) <= body_chars else f"\n\n[truncated to {body_chars} of {len(body)} chars]"
    console.print(f"Body preview for {message['id']}:")
    console.print(_safe(f"{preview}{suffix}", console))


def _message_time(message: dict[str, Any]) -> str:
    return str(message["received_at"] or message["sent_at"] or "")


def _safe(value: str, console: Any) -> str:
    return safe_console_text(str(value), console)
