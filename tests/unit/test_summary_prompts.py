from __future__ import annotations

from datetime import date

from app.ai.summary_prompts import DAILY_PROMPT, WEEKLY_PROMPT, build_weekly_context


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


def test_weekly_prompt_builds_on_prior_weeks() -> None:
    lower = WEEKLY_PROMPT.lower()
    assert "prior weekly summaries" in lower or "last week" in lower
    assert "build on" in lower


def test_build_weekly_context_is_blank_without_priors() -> None:
    assert build_weekly_context([]) == ""


def test_build_weekly_context_renders_weeks_oldest_first() -> None:
    ctx = build_weekly_context(
        [
            (date(2026, 4, 27), date(2026, 5, 3), "Focused on sleep."),
            (date(2026, 5, 4), date(2026, 5, 10), "Sleep improved, mood up."),
        ]
    )
    assert "2026-04-27" in ctx and "2026-05-03" in ctx
    assert "Focused on sleep." in ctx and "Sleep improved, mood up." in ctx
    # Oldest week appears before the newer one.
    assert ctx.index("Focused on sleep.") < ctx.index("Sleep improved, mood up.")
