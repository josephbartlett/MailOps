"""Proton Bridge discovery primitives."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, SecretStr

from mailops.core.config import AppConfig

DEFAULT_HOST = "127.0.0.1"
DEFAULT_IMAP_PORT = 1143
DEFAULT_SMTP_PORT = 1025
DEFAULT_IMAP_SECURITY = "plain"
CONFIG_SECTION = "providers.proton_bridge"


class BridgeDiscoveryOverrides(BaseModel):
    profile_name: str | None = None
    host: str | None = None
    imap_port: int | None = None
    smtp_port: int | None = None
    imap_security: str | None = None
    username: str | None = None
    password: SecretStr | None = None
    account_email: str | None = None
    canonical_email: str | None = None
    config_path: Path | None = None


class BridgeEndpoint(BaseModel):
    profile_name: str | None = None
    host: str = DEFAULT_HOST
    imap_port: int = DEFAULT_IMAP_PORT
    smtp_port: int = DEFAULT_SMTP_PORT
    imap_security: str = DEFAULT_IMAP_SECURITY
    username: str | None = None
    password: SecretStr | None = None
    account_email: str | None = None
    canonical_email: str | None = None
    source: str = "defaults"
    config_path: Path | None = None

    def password_present(self) -> bool:
        return self.password is not None and bool(self.password.get_secret_value())

    def is_usable(self) -> bool:
        return bool(self.username and self.password_present())

    def resolved_account_id(self) -> str:
        identifier = self.canonical_email or self.account_email or self.username or "proton_bridge_default"
        return identifier.strip().lower()

    def redacted_summary(self) -> dict[str, str]:
        return {
            "source": self.source,
            "host": self.host,
            "imap_port": str(self.imap_port),
            "smtp_port": str(self.smtp_port),
            "imap_security": self.imap_security,
            "username": self.username or "(unset)",
            "password_present": str(self.password_present()).lower(),
            "account_email": self.account_email or "(unset)",
            "canonical_email": self.canonical_email or "(unset)",
            "profile_name": self.profile_name or "(unset)",
            "config_path": str(self.config_path) if self.config_path is not None else "(none)",
            "usable": str(self.is_usable()).lower(),
        }


def _parse_scalar(raw_value: str) -> object:
    value = raw_value.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        return value


def _read_section_from_config(path: Path, section_name: str) -> dict[str, object]:
    if not path.exists():
        return {}

    active_section = ""
    section_values: dict[str, object] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            active_section = line[1:-1].strip()
            continue
        if active_section != section_name or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        section_values[key.strip()] = _parse_scalar(raw_value)
    return section_values


def _endpoint_from_mapping(values: Mapping[str, object], *, source: str, config_path: Path | None = None) -> BridgeEndpoint | None:
    if not values:
        return None

    password = values.get("password")
    if isinstance(password, SecretStr):
        secret = password
    elif isinstance(password, str) and password:
        secret = SecretStr(password)
    else:
        secret = None

    return BridgeEndpoint(
        profile_name=str(values["profile_name"]) if values.get("profile_name") else None,
        host=str(values.get("host", DEFAULT_HOST)),
        imap_port=int(values.get("imap_port", DEFAULT_IMAP_PORT)),
        smtp_port=int(values.get("smtp_port", DEFAULT_SMTP_PORT)),
        imap_security=str(values.get("imap_security", DEFAULT_IMAP_SECURITY)),
        username=str(values["username"]) if values.get("username") else None,
        password=secret,
        account_email=str(values["account_email"]) if values.get("account_email") else None,
        canonical_email=str(values["canonical_email"]) if values.get("canonical_email") else None,
        source=source,
        config_path=config_path,
    )


def _config_path_for(config: AppConfig | None, overrides: BridgeDiscoveryOverrides | None, env: Mapping[str, str]) -> Path | None:
    if overrides is not None and overrides.config_path is not None:
        return overrides.config_path
    if "MAILOPS_PROTON_CONFIG_FILE" in env:
        return Path(env["MAILOPS_PROTON_CONFIG_FILE"]).expanduser()
    if config is not None:
        return config.config_dir / "config.toml"
    return None


def discover_bridge(
    config: AppConfig | None = None,
    *,
    overrides: BridgeDiscoveryOverrides | None = None,
    env: Mapping[str, str] | None = None,
) -> BridgeEndpoint:
    """Resolve Bridge connection settings from config, env, and explicit overrides."""

    environment = os.environ if env is None else env
    endpoint = BridgeEndpoint()

    config_path = _config_path_for(config, overrides, environment)
    config_values = _read_section_from_config(config_path, CONFIG_SECTION) if config_path is not None else {}
    config_endpoint = _endpoint_from_mapping(config_values, source="config_file", config_path=config_path)
    if config_endpoint is not None:
        endpoint = config_endpoint

    env_values = {
        "host": environment.get("MAILOPS_PROTON_HOST"),
        "imap_port": environment.get("MAILOPS_PROTON_IMAP_PORT"),
        "smtp_port": environment.get("MAILOPS_PROTON_SMTP_PORT"),
        "imap_security": environment.get("MAILOPS_PROTON_IMAP_SECURITY"),
        "username": environment.get("MAILOPS_PROTON_USERNAME"),
        "password": environment.get("MAILOPS_PROTON_PASSWORD"),
        "account_email": environment.get("MAILOPS_PROTON_ACCOUNT_EMAIL"),
        "canonical_email": environment.get("MAILOPS_PROTON_CANONICAL_EMAIL"),
    }
    env_payload = {key: value for key, value in env_values.items() if value not in (None, "")}
    env_endpoint = _endpoint_from_mapping(env_payload, source="env", config_path=config_path)
    if env_endpoint is not None:
        update_payload = {}
        for key in env_payload:
            update_payload[key] = getattr(env_endpoint, key)
        endpoint = endpoint.model_copy(update=update_payload)
        endpoint.source = "env"
        endpoint.config_path = config_path

    if overrides is not None:
        override_payload = overrides.model_dump(exclude_none=True)
        if override_payload:
            endpoint = endpoint.model_copy(update=override_payload)
            endpoint.source = "explicit"
            endpoint.config_path = config_path

    if config_path is not None:
        endpoint.config_path = config_path
    return endpoint
