from __future__ import annotations

from mailops.adapters.gmail.adapter import GmailApiAdapter


def test_gmail_adapter_declares_no_runtime_capabilities_until_implemented() -> None:
    capabilities = GmailApiAdapter.capabilities

    assert capabilities.sync is False
    assert capabilities.drafts is False
    assert capabilities.send is False
    assert capabilities.labels is False
    assert capabilities.rules is False
