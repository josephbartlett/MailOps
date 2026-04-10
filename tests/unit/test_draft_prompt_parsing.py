from __future__ import annotations

from mailops.agent.drafts import _search_tokens, _since_days_for_prompt


def test_day_window_words_do_not_become_search_tokens() -> None:
    prompt = "draft replies for messages from the last 365 days"

    assert _since_days_for_prompt(prompt) == 365
    assert _search_tokens(prompt) == set()
