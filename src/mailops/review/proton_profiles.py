"""Shared Proton profile resolution for review-time provider actions."""

from __future__ import annotations

from mailops.adapters.proton_bridge.bridge_discovery import BridgeDiscoveryOverrides
from mailops.adapters.proton_bridge.registry import (
    find_matching_profiles,
    get_profile,
    merge_overrides,
    profile_to_overrides,
)
from mailops.core.config import AppConfig
from mailops.core.exceptions import AdapterError
from mailops.index.db import connect_db


def resolve_proton_overrides(
    config: AppConfig,
    *,
    account_id: str,
    account_email: str,
    adapter_config_ref: str | None,
    explicit: BridgeDiscoveryOverrides | None,
) -> BridgeDiscoveryOverrides:
    """Resolve the saved Proton profile plus transient operator overrides."""

    profile_overrides = BridgeDiscoveryOverrides(
        username=account_email,
        account_email=account_email,
        canonical_email=account_id,
    )
    if adapter_config_ref:
        saved_profile = get_profile(config, adapter_config_ref)
        if saved_profile is None:
            raise AdapterError(f"Saved Proton profile '{adapter_config_ref}' is required for account '{account_id}'.")
        profile_overrides = profile_to_overrides(saved_profile)
    else:
        matches = find_matching_profiles(config, account_email) or find_matching_profiles(config, account_id)
        if len(matches) > 1:
            raise AdapterError(
                f"Multiple Proton profiles match account '{account_id}'. Save or sync with a single explicit profile first."
            )
        if len(matches) == 1:
            profile_overrides = profile_to_overrides(matches[0])
    resolved = merge_overrides(profile_overrides, explicit)
    allowed = {account_id.strip().lower(), account_email.strip().lower()}
    with connect_db(config.db_path) as connection:
        aliases = connection.execute(
            "SELECT alias_email, provider_username FROM account_aliases WHERE account_id = ?", (account_id,)
        ).fetchall()
    allowed.update(str(row["alias_email"]).strip().lower() for row in aliases)
    allowed_usernames = {account_email.strip().lower()}
    allowed_usernames.update(str(row["alias_email"]).strip().lower() for row in aliases)
    allowed_usernames.update(
        str(row["provider_username"]).strip().lower() for row in aliases if row["provider_username"]
    )
    if profile_overrides.username:
        allowed_usernames.add(profile_overrides.username.strip().lower())
    for candidate in (profile_overrides, explicit, resolved):
        if candidate is None:
            continue
        for identity in (candidate.account_email, candidate.canonical_email):
            if identity is not None and identity.strip().lower() not in allowed:
                raise AdapterError("Proton profile identity does not match the reviewed draft account.")
        if candidate.username is not None and candidate.username.strip().lower() not in allowed_usernames:
            raise AdapterError("Proton login username does not match the saved profile or known aliases for the reviewed draft account.")
    return resolved
