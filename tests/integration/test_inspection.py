from __future__ import annotations

from mailops.core.config import AppConfig
from mailops.demo.seed import seed_demo_mailbox
from mailops.index.inspection import get_message_detail, get_thread_detail
from mailops.index.search import SearchRequest, search_messages


def test_search_results_can_be_inspected_by_thread_and_message_id(tmp_path) -> None:
    config = AppConfig(home_dir=tmp_path / ".mailops")
    seed_demo_mailbox(config)

    search_results = search_messages(config, SearchRequest(query="invoice"))

    assert search_results
    result = search_results[0]
    assert result["thread_id"] == "demo-thread-finance"
    assert result["message_id"] == "demo-message-finance"

    thread_detail = get_thread_detail(config, result["thread_id"])
    assert thread_detail is not None
    assert thread_detail["thread"]["subject"] == "Invoice approval needed"
    assert thread_detail["messages"][0]["id"] == "demo-message-finance"
    assert "invoice" in thread_detail["messages"][0]["body_text"].lower()

    message_detail = get_message_detail(config, result["message_id"])
    assert message_detail is not None
    assert message_detail["thread"]["id"] == "demo-thread-finance"
    assert message_detail["message"]["sender"] == "vendor@example.com"
