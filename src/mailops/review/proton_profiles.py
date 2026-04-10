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
    return merge_overrides(profile_overrides, explicit)
