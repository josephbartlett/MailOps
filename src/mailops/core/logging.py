"""Logging configuration for MailOps."""

from __future__ import annotations

import logging
from copy import copy
from logging.handlers import RotatingFileHandler
import re

from mailops.core.config import AppConfig

_SENSITIVE_PATTERNS = (
    re.compile(
        r'''(?i)(["']?\b(?:password|(?:access_|refresh_)?token|api[_-]?key|authorization)["']?\s*[=:]\s*)'''
        r'''(?:"[^"\r\n]*"|'[^'\r\n]*'|(?:Bearer|Basic)\s+[^\s,;}]+|[^\s,;}]+)'''
    ),
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


class RedactingFormatter(logging.Formatter):
    """Redact the final formatted text, including exception and stack details."""

    def format(self, record: logging.LogRecord) -> str:
        sanitized_record = copy(record)
        sanitized_record.exc_text = None
        return redact_text(super().format(sanitized_record))


def configure_logging(config: AppConfig, *, force: bool = False) -> logging.Logger:
    """Create or return the package logger."""

    logger = logging.getLogger("mailops")
    settings = (str(config.log_path.resolve()), config.log_level.upper(), config.redact_logs)
    if getattr(logger, "_mailops_settings", None) == settings and not force:
        return logger

    for existing_handler in logger.handlers:
        existing_handler.close()
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

    formatter_class = RedactingFormatter if config.redact_logs else logging.Formatter
    formatter = formatter_class("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler = RotatingFileHandler(config.log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(formatter)
    if config.redact_logs:
        handler.addFilter(RedactionFilter())
    logger.addHandler(handler)
    logger._mailops_configured = True  # type: ignore[attr-defined]
    logger._mailops_settings = settings  # type: ignore[attr-defined]
    return logger
