from __future__ import annotations

import pytest
from pydantic import SecretStr
import typer

from mailops.adapters.proton_bridge.adapter import ProtonBridgeAdapter
from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.adapters.proton_bridge.registry import ProtonAccountProfile, save_profile
from mailops.cli.commands.sync import _resolve_sync_targets
from mailops.core.config import AppConfig


def _save_test_profiles(config: AppConfig) -> None:
    save_profile(
        config,
        ProtonAccountProfile(
            profile_name="work",
            host="127.0.0.1",
            imap_port=1143,
            smtp_port=1025,
            imap_security="plain",
            username="operator@example.com",
            account_email="operator@example.com",
            canonical_email="operator@example.com",
        ),
    )
    save_profile(
        config,
        ProtonAccountProfile(
            profile_name="alias",
            host="127.0.0.1",
            imap_port=1143,
            smtp_port=1025,
            imap_security="plain",
            username="alias@example.com",
            account_email="alias@example.com",
            canonical_email="operator@example.com",
        ),
    )


def test_resolve_sync_targets_uses_all_saved_profiles_when_account_is_all(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    _save_test_profiles(config)
    adapter = ProtonBridgeAdapter(config)

    targets = _resolve_sync_targets(
        profile=None,
        account="all",
        explicit_overrides=BridgeDiscoveryOverrides(password=SecretStr("bridge-pass")),
        adapter=adapter,
    )

    assert [target.label for target in targets] == ["alias", "work"]
    assert all(target.request_account_id is None for target in targets)
    assert all(target.overrides.password is not None for target in targets)


def test_resolve_sync_targets_matches_canonical_account_to_multiple_profiles(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    _save_test_profiles(config)
    adapter = ProtonBridgeAdapter(config)

    targets = _resolve_sync_targets(
        profile=None,
        account="operator@example.com",
        explicit_overrides=BridgeDiscoveryOverrides(password=SecretStr("bridge-pass")),
        adapter=adapter,
    )

    assert [target.label for target in targets] == ["alias", "work"]
    assert all(target.request_account_id is None for target in targets)


def test_resolve_sync_targets_rejects_identity_override_for_multi_profile_sync(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    _save_test_profiles(config)
    adapter = ProtonBridgeAdapter(config)

    with pytest.raises(typer.BadParameter):
        _resolve_sync_targets(
            profile="all",
            account="all",
            explicit_overrides=BridgeDiscoveryOverrides(
                username="override@example.com",
                password=SecretStr("bridge-pass"),
            ),
            adapter=adapter,
        )
