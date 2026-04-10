"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, Field, model_validator


def _env_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


class AppConfig(BaseModel):
    """Local runtime configuration for MailOps."""

    app_name: str = "MailOps"
    environment: str = Field(default_factory=lambda: os.getenv("MAILOPS_ENV", "development"))
    home_dir: Path = Field(default_factory=lambda: Path(os.getenv("MAILOPS_HOME", ".mailops")).expanduser())
    data_dir: Path | None = None
    state_dir: Path | None = None
    config_dir: Path | None = None
    log_dir: Path | None = None
    db_path: Path | None = None
    log_path: Path | None = None
    log_level: str = Field(default_factory=lambda: os.getenv("MAILOPS_LOG_LEVEL", "INFO"))
    redact_logs: bool = Field(default_factory=lambda: _env_bool(os.getenv("MAILOPS_REDACT_LOGS"), default=True))
    default_provider: str = Field(default_factory=lambda: os.getenv("MAILOPS_DEFAULT_PROVIDER", "proton_bridge"))
    model_provider: str = Field(default_factory=lambda: os.getenv("MAILOPS_MODEL_PROVIDER", "openai"))

    @model_validator(mode="after")
    def populate_paths(self) -> "AppConfig":
        """Fill derived path fields when omitted."""

        if self.data_dir is None:
            self.data_dir = self.home_dir / "data"
        if self.state_dir is None:
            self.state_dir = self.home_dir / "state"
        if self.config_dir is None:
            self.config_dir = self.home_dir / "config"
        if self.log_dir is None:
            self.log_dir = self.home_dir / "logs"
        if self.db_path is None:
            self.db_path = self.state_dir / "mailops.db"
        if self.log_path is None:
            self.log_path = self.log_dir / "mailops.log"
        return self

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AppConfig":
        """Create config from an environment mapping."""

        source = os.environ if env is None else env
        payload: dict[str, object] = {}
        if "MAILOPS_ENV" in source:
            payload["environment"] = source["MAILOPS_ENV"]
        if "MAILOPS_HOME" in source:
            payload["home_dir"] = Path(source["MAILOPS_HOME"]).expanduser()
        if "MAILOPS_LOG_LEVEL" in source:
            payload["log_level"] = source["MAILOPS_LOG_LEVEL"]
        if "MAILOPS_REDACT_LOGS" in source:
            payload["redact_logs"] = _env_bool(source["MAILOPS_REDACT_LOGS"], default=True)
        if "MAILOPS_DEFAULT_PROVIDER" in source:
            payload["default_provider"] = source["MAILOPS_DEFAULT_PROVIDER"]
        if "MAILOPS_MODEL_PROVIDER" in source:
            payload["model_provider"] = source["MAILOPS_MODEL_PROVIDER"]
        return cls(**payload)

    def ensure_directories(self) -> None:
        """Create required local directories."""

        for directory in (self.home_dir, self.data_dir, self.state_dir, self.config_dir, self.log_dir):
            directory.mkdir(parents=True, exist_ok=True)

