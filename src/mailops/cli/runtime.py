"""Shared runtime helpers for CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from logging import Logger

from rich.console import Console

from mailops.core.config import AppConfig
from mailops.core.logging import configure_logging
from mailops.index.db import initialize_database


@dataclass(slots=True)
class Runtime:
    """Shared objects each CLI command can rely on."""

    config: AppConfig
    console: Console
    logger: Logger


def build_runtime() -> Runtime:
    """Load config, ensure local state exists, and configure logging."""

    config = AppConfig.from_env()
    config.ensure_directories()
    logger = configure_logging(config)
    initialize_database(config)
    return Runtime(config=config, console=Console(), logger=logger)

