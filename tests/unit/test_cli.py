from __future__ import annotations

import pytest
from typer.testing import CliRunner

from mailops.cli.main import app

runner = CliRunner()


@pytest.mark.parametrize(
    "args",
    [
        ["doctor"],
        ["connect"],
        ["connect", "proton"],
        ["connect", "proton", "--list-profiles"],
        ["demo"],
        ["demo", "seed"],
        ["draft", "--help"],
        ["draft", "create", "--to", "client@example.com", "--subject", "Hello", "--body", "Draft body"],
        ["sync"],
        ["status"],
        ["search", "invoice"],
        ["inspect", "--help"],
        ["inspect", "thread", "missing-thread"],
        ["inspect", "message", "missing-message"],
        ["triage"],
        ["ask", "show unanswered client threads older than 2 days"],
        ["review"],
        ["review", "batch", "list"],
        ["review", "batch", "show", "batch_001"],
        ["review", "batch", "sync-drafts", "batch_001"],
        ["rules"],
        ["rules", "propose", "filter future messages from vendor.example to label Finance"],
        ["apply", "batch_001"],
        ["rollback", "batch_001"],
        ["export"],
        ["export", "audit"],
    ],
)
def test_cli_commands_smoke(tmp_path, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    monkeypatch.setenv("MAILOPS_HOME", str(tmp_path / ".mailops"))
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
