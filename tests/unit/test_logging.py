from __future__ import annotations

import logging

import pytest

from mailops.core.config import AppConfig
from mailops.core.logging import RedactingFormatter, configure_logging, redact_text


@pytest.mark.parametrize("text", [
    "Authorization: Bearer sensitive-token",
    "authorization=Basic sensitive-token",
    '{"password": "sensitive-token with spaces"}',
    "refresh_token='sensitive-token'",
    "api_key=sensitive-token",
])
def test_redaction_removes_complete_credentials(text):
    assert "sensitive-token" not in redact_text(text)


def test_formatter_redacts_exception_details():
    try:
        raise RuntimeError("Authorization: Bearer sensitive-token")
    except RuntimeError:
        import sys
        record = logging.LogRecord("mailops", logging.ERROR, __file__, 1, "Connection failed", (), sys.exc_info())
    formatted = RedactingFormatter("%(message)s").format(record)
    assert "sensitive-token" not in formatted
    assert "RuntimeError" in formatted


def test_logger_switches_homes_without_reusing_previous_file(tmp_path):
    first = AppConfig(home_dir=tmp_path / "first")
    second = AppConfig(home_dir=tmp_path / "second")
    first.ensure_directories()
    second.ensure_directories()
    configure_logging(first).info("first-only")
    configure_logging(second).info("second-only")
    assert "second-only" not in first.log_path.read_text(encoding="utf-8")
    assert "second-only" in second.log_path.read_text(encoding="utf-8")
