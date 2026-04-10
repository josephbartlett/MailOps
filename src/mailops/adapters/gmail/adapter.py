"""Gmail adapter shell."""

from __future__ import annotations

from mailops.adapters.base import AdapterCapabilities


class GmailApiAdapter:
    """Provider-aware shell for future Gmail API support."""

    provider_name = "gmail_api"
    capabilities = AdapterCapabilities(sync=True, drafts=True, send=True, labels=True, rules=False)

    def describe(self) -> str:
        return "Gmail API adapter shell for OAuth-based mailbox operations."

