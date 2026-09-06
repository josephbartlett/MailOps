from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
import pytest

from mailops.adapters.proton_bridge.bridge_discovery import (
    BridgeDiscoveryOverrides,
    DEFAULT_HOST,
    DEFAULT_IMAP_PORT,
    DEFAULT_SMTP_PORT,
    discover_bridge,
)
from mailops.core.config import AppConfig
from mailops.core.exceptions import AdapterError


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


def test_toml_password_preserves_hash_quotes_and_backslashes(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    config.ensure_directories()
    (config.config_dir / "config.toml").write_text(
        '[providers.proton_bridge]\nusername = "ops"\npassword = \'space # " quote \\ backslash\' # actual comment\n',
        encoding="utf-8",
    )
    endpoint = discover_bridge(config, env={})
    assert endpoint.password.get_secret_value() == 'space # " quote \\ backslash'


def test_malformed_toml_does_not_expose_configuration_content(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    config.ensure_directories()
    (config.config_dir / "config.toml").write_text(
        '[providers.proton_bridge]\npassword = "private-secret', encoding="utf-8"
    )
    with pytest.raises(AdapterError) as error:
        discover_bridge(config, env={})
    assert "private-secret" not in str(error.value)


def test_unknown_security_mode_cannot_fall_back_to_plaintext(tmp_path) -> None:
    with pytest.raises(ValueError):
        discover_bridge(AppConfig(home_dir=tmp_path), env={"MAILOPS_PROTON_IMAP_SECURITY": "tls"})
