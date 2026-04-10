from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from mailops.adapters.proton_bridge.bridge_discovery import (
    BridgeDiscoveryOverrides,
    DEFAULT_HOST,
    DEFAULT_IMAP_PORT,
    DEFAULT_SMTP_PORT,
    discover_bridge,
)
from mailops.core.config import AppConfig


def test_discover_bridge_uses_defaults_when_no_settings_exist(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")

    endpoint = discover_bridge(config, env={})

    assert endpoint.host == DEFAULT_HOST
    assert endpoint.imap_port == DEFAULT_IMAP_PORT
    assert endpoint.smtp_port == DEFAULT_SMTP_PORT
    assert endpoint.source == "defaults"
    assert endpoint.is_usable() is False


def test_discover_bridge_merges_config_env_and_explicit_overrides(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    config.ensure_directories()
    config_file = config.config_dir / "config.toml"
    config_file.write_text(
        "\n".join(
            [
                "[providers.proton_bridge]",
                'host = "bridge.local"',
                "imap_port = 2143",
                "smtp_port = 2025",
                'username = "config-user"',
                'password = "config-pass"',
            ]
        ),
        encoding="utf-8",
    )

    endpoint = discover_bridge(
        config,
        overrides=BridgeDiscoveryOverrides(host="127.0.0.9", password=SecretStr("explicit-pass")),
        env={
            "MAILOPS_PROTON_CONFIG_FILE": str(config_file),
            "MAILOPS_PROTON_USERNAME": "env-user",
            "MAILOPS_PROTON_ACCOUNT_EMAIL": "ops@example.com",
            "MAILOPS_PROTON_CANONICAL_EMAIL": "primary@example.com",
        },
    )

    assert endpoint.host == "127.0.0.9"
    assert endpoint.imap_port == 2143
    assert endpoint.smtp_port == 2025
    assert endpoint.username == "env-user"
    assert endpoint.password is not None
    assert endpoint.password.get_secret_value() == "explicit-pass"
    assert endpoint.account_email == "ops@example.com"
    assert endpoint.canonical_email == "primary@example.com"
    assert endpoint.source == "explicit"
    assert endpoint.config_path == Path(config_file)
    assert endpoint.is_usable() is True
