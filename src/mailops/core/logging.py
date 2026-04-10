"""Logging configuration for MailOps."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import re

from mailops.core.config import AppConfig

_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(password\s*[=:]\s*)(\S+)"),
    re.compile(r"(?i)(token\s*[=:]\s*)(\S+)"),
    re.compile(r"(?i)(authorization\s*[=:]\s*)(\S+)"),
)


def redact_text(text: str) -> str:
    """Redact obvious credential-shaped fragments from a string."""

    result = text
    for pattern in _SENSITIVE_PATTERNS:
        result = pattern.sub(r"\1[REDACTED]", result)
    return result


class RedactionFilter(logging.Filter):
    """Best-effort log record redaction."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        record.msg = redact_text(message)
        record.args = ()
        return True


def configure_logging(config: AppConfig, *, force: bool = False) -> logging.Logger:
    """Create or return the package logger."""

    logger = logging.getLogger("mailops")
    if getattr(logger, "_mailops_configured", False) and not force:
        return logger

    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler = RotatingFileHandler(config.log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(formatter)
    if config.redact_logs:
        handler.addFilter(RedactionFilter())
    logger.addHandler(handler)
    logger._mailops_configured = True  # type: ignore[attr-defined]
    return logger

