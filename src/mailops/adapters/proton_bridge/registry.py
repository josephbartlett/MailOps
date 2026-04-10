"""Persistent non-secret Proton profile registry."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from mailops.adapters.proton_bridge.bridge_discovery import (
    BridgeDiscoveryOverrides,
    DEFAULT_HOST,
    DEFAULT_IMAP_PORT,
    DEFAULT_IMAP_SECURITY,
    DEFAULT_SMTP_PORT,
)
from mailops.core.config import AppConfig


class ProtonAccountProfile(BaseModel):
    profile_name: str
    host: str = DEFAULT_HOST
    imap_port: int = DEFAULT_IMAP_PORT
    smtp_port: int = DEFAULT_SMTP_PORT
    imap_security: str = DEFAULT_IMAP_SECURITY
    username: str
    account_email: str
    canonical_email: str | None = None


class ProtonAccountRegistry(BaseModel):
    profiles: list[ProtonAccountProfile] = Field(default_factory=list)


def registry_path(config: AppConfig) -> Path:
    return config.config_dir / "proton_accounts.json"


def load_registry(config: AppConfig) -> ProtonAccountRegistry:
    path = registry_path(config)
    if not path.exists():
        return ProtonAccountRegistry()
    return ProtonAccountRegistry.model_validate_json(path.read_text(encoding="utf-8"))


def save_registry(config: AppConfig, registry: ProtonAccountRegistry) -> None:
    config.ensure_directories()
    path = registry_path(config)
    payload = registry.model_dump_json(indent=2)
    path.write_text(payload + "\n", encoding="utf-8")


def list_profiles(config: AppConfig) -> list[ProtonAccountProfile]:
    return sorted(load_registry(config).profiles, key=lambda profile: profile.profile_name.lower())


def get_profile(config: AppConfig, profile_name: str) -> ProtonAccountProfile | None:
    normalized = profile_name.strip().lower()
    for profile in load_registry(config).profiles:
        if profile.profile_name.lower() == normalized:
            return profile
    return None


def find_matching_profiles(config: AppConfig, selector: str) -> list[ProtonAccountProfile]:
    normalized = selector.strip().lower()
    if not normalized:
        return []
    matches: list[ProtonAccountProfile] = []
    for profile in list_profiles(config):
        identifiers = {
            profile.profile_name.strip().lower(),
            profile.username.strip().lower(),
            profile.account_email.strip().lower(),
        }
        if profile.canonical_email:
            identifiers.add(profile.canonical_email.strip().lower())
        if normalized in identifiers:
            matches.append(profile)
    return matches


def save_profile(config: AppConfig, profile: ProtonAccountProfile) -> None:
    registry = load_registry(config)
    replaced = False
    for index, existing in enumerate(registry.profiles):
        if existing.profile_name.lower() == profile.profile_name.lower():
            registry.profiles[index] = profile
            replaced = True
            break
    if not replaced:
        registry.profiles.append(profile)
    save_registry(config, registry)


def profile_to_overrides(profile: ProtonAccountProfile) -> BridgeDiscoveryOverrides:
    return BridgeDiscoveryOverrides(
        profile_name=profile.profile_name,
        host=profile.host,
        imap_port=profile.imap_port,
        smtp_port=profile.smtp_port,
        imap_security=profile.imap_security,
        username=profile.username,
        account_email=profile.account_email,
        canonical_email=profile.canonical_email,
    )


def merge_overrides(base: BridgeDiscoveryOverrides | None, explicit: BridgeDiscoveryOverrides | None) -> BridgeDiscoveryOverrides:
    payload: dict[str, object] = {}
    if base is not None:
        payload.update(base.model_dump(exclude_none=True))
    if explicit is not None:
        payload.update(explicit.model_dump(exclude_none=True))
    return BridgeDiscoveryOverrides(**payload)
