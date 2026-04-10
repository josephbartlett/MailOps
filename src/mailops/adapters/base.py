"""Base adapter types."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class AdapterCapabilities(BaseModel):
    """Declared capabilities for a provider adapter."""

    sync: bool = False
    drafts: bool = False
    send: bool = False
    labels: bool = False
    rules: bool = False


class ProviderAdapter(Protocol):
    """Protocol implemented by concrete provider adapters."""

    provider_name: str
    capabilities: AdapterCapabilities

    def describe(self) -> str:
        """Return a short human-readable description."""

