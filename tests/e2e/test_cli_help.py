from __future__ import annotations

from typer.testing import CliRunner

from mailops.cli.main import app


def test_cli_help_lists_primary_commands(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MAILOPS_HOME", str(tmp_path / ".mailops"))
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "doctor" in result.output
    assert "demo" in result.output
    assert "review" in result.output
    assert "rules" in result.output
    assert "export" in result.output
