"""Typer entrypoint for MailOps."""

from __future__ import annotations

import typer

from mailops.cli.commands.apply import apply_command
from mailops.cli.commands.ask import ask_command
from mailops.cli.commands.connect import connect_command
from mailops.cli.commands.demo import demo_app
from mailops.cli.commands.draft import draft_app
from mailops.cli.commands.doctor import doctor_command
from mailops.cli.commands.export import export_app
from mailops.cli.commands.inspect import inspect_app
from mailops.cli.commands.review import review_app
from mailops.cli.commands.rollback import rollback_command
from mailops.cli.commands.rules import rules_app
from mailops.cli.commands.search import search_command
from mailops.cli.commands.status import status_command
from mailops.cli.commands.sync import sync_command
from mailops.cli.commands.triage import triage_command

app = typer.Typer(
    help="MailOps: local-first inbox operations harness for serious workflows.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

app.command("doctor")(doctor_command)
app.command("connect")(connect_command)
app.add_typer(demo_app, name="demo")
app.add_typer(draft_app, name="draft")
app.command("sync")(sync_command)
app.command("status")(status_command)
app.command("search")(search_command)
app.add_typer(inspect_app, name="inspect")
app.command("triage")(triage_command)
app.command("ask")(ask_command)
app.add_typer(review_app, name="review")
app.add_typer(rules_app, name="rules")
app.command("apply")(apply_command)
app.command("rollback")(rollback_command)
app.add_typer(export_app, name="export")


def main() -> None:
    """Invoke the CLI application."""

    app()


if __name__ == "__main__":
    main()
