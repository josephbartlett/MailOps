from __future__ import annotations

import pytest
from typer.testing import CliRunner

from mailops.cli.main import app

runner = CliRunner()


@pytest.mark.parametrize(
    ("args", "expected_exit_code"),
    [
        (["doctor"], 0),
        (["connect"], 0),
        (["connect", "proton"], 0),
        (["connect", "proton", "--list-profiles"], 0),
        (["demo"], 0),
        (["demo", "seed"], 0),
        (["draft", "--help"], 0),
        (["draft", "create", "--to", "client@example.com", "--subject", "Hello", "--body", "Draft body"], 1),
        (["sync"], 1),
        (["status"], 0),
        (["search", "invoice"], 0),
        (["inspect", "--help"], 0),
        (["inspect", "thread", "missing-thread"], 0),
        (["inspect", "message", "missing-message"], 0),
        (["triage"], 0),
        (["ask", "show unanswered client threads older than 2 days"], 0),
        (["review"], 0),
        (["review", "batch", "list"], 0),
        (["review", "batch", "show", "batch_001"], 0),
        (["review", "batch", "sync-drafts", "batch_001"], 0),
        (["rules"], 0),
        (["rules", "propose", "filter future messages from vendor.example to label Finance"], 0),
        (["apply", "batch_001"], 1),
        (["rollback", "batch_001"], 0),
        (["export"], 0),
        (["export", "audit"], 0),
    ],
)
def test_cli_commands_smoke(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    expected_exit_code: int,
) -> None:
    monkeypatch.setenv("MAILOPS_HOME", str(tmp_path / ".mailops"))
    result = runner.invoke(app, args)
    assert result.exit_code == expected_exit_code, result.output
