from __future__ import annotations

from app.ai.summary_prompts import DAILY_PROMPT, WEEKLY_PROMPT


def test_weekly_pulls_events_not_just_averages() -> None:
    assert "query_entries" in WEEKLY_PROMPT
    assert "thought_record" in WEEKLY_PROMPT
    assert "trigger" in WEEKLY_PROMPT
    # Still uses averages for trends.
    assert "daily_summary" in WEEKLY_PROMPT


def test_weekly_asks_for_cause_effect_links() -> None:
    lower = WEEKLY_PROMPT.lower()
    assert "cause" in lower or "→" in WEEKLY_PROMPT or "led" in lower
    # Keeps the mood + energy + anxiety chart (charted-metrics regression).
    assert "mood" in lower and "energy" in lower and "anxiety" in lower


def test_daily_reads_events_in_order() -> None:
    lower = DAILY_PROMPT.lower()
    assert "query_entries" in DAILY_PROMPT
    assert "order" in lower or "times" in lower
