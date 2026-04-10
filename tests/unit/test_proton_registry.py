from __future__ import annotations

from mailops.adapters.proton_bridge.registry import (
    ProtonAccountProfile,
    find_matching_profiles,
    get_profile,
    list_profiles,
    save_profile,
)
from mailops.core.config import AppConfig


def test_save_and_load_proton_profile_registry(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    config.ensure_directories()

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

    profiles = list_profiles(config)
    assert [profile.profile_name for profile in profiles] == ["alias", "work"]
    alias_profile = get_profile(config, "alias")
    assert alias_profile is not None
    assert alias_profile.canonical_email == "operator@example.com"


def test_find_matching_profiles_matches_profile_alias_and_canonical_email(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    config.ensure_directories()

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

    by_profile = find_matching_profiles(config, "work")
    assert [profile.profile_name for profile in by_profile] == ["work"]

    by_alias = find_matching_profiles(config, "alias@example.com")
    assert [profile.profile_name for profile in by_alias] == ["alias"]

    by_canonical = find_matching_profiles(config, "operator@example.com")
    assert [profile.profile_name for profile in by_canonical] == ["alias", "work"]
