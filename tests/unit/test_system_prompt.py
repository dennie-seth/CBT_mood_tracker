from __future__ import annotations

from app.ai.prompts import SYSTEM_PROMPT


def test_prompt_includes_scale_polarity() -> None:
    assert "Higher is better" in SYSTEM_PROMPT
    assert "Higher is worse" in SYSTEM_PROMPT
    assert "Mood" in SYSTEM_PROMPT


def test_prompt_includes_timeline_guidance() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "chronological" in lower
    assert "local timezone" in lower
    assert "query_entries" in SYSTEM_PROMPT
    # daily_summary should be steered toward trends, not causal questions.
    assert "erases timing" in lower or "collapses a day" in lower


def test_prompt_explains_migraine_entries() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "migraine" in lower
    # The assistant should know where the episode details live and to look
    # at the run-up to an attack for triggers.
    assert "duration_minutes" in SYSTEM_PROMPT
    assert "before" in lower


def test_prompt_mentions_migraine_stats_tool_and_medication_guidance() -> None:
    assert "migraine_stats" in SYSTEM_PROMPT
    assert "peak_intensity" in SYSTEM_PROMPT
    assert "triggers" in SYSTEM_PROMPT
    lower = SYSTEM_PROMPT.lower()
    assert "doctor" in lower
    assert "dosing" in lower  # never give dosing advice


def test_prompt_explains_activation_ratings() -> None:
    assert "predicted_effect" in SYSTEM_PROMPT and "actual_effect" in SYSTEM_PROMPT
    assert "not a mood value" in SYSTEM_PROMPT.lower()


# --- precision & self-check (prompt quality pass) ---------------------------

def test_prompt_demands_plain_text_for_telegram() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "plain text" in lower
    assert "markdown" in lower  # explicitly forbidden


def test_prompt_has_a_final_self_check() -> None:
    assert "Before you reply" in SYSTEM_PROMPT
    lower = SYSTEM_PROMPT.lower()
    for item in ("number", "weekday", "order", "scale", "language"):
        assert item in lower, item


def test_prompt_separates_sequence_from_causation() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "followed" in lower and "caused" in lower
    assert "recorded_at" in SYSTEM_PROMPT
    # Weekdays come from the tool output, not mental arithmetic.
    assert "weekday" in lower


def test_prompt_flags_placeholder_noon_times() -> None:
    assert "12:00" in SYSTEM_PROMPT


def test_prompt_treats_entry_text_as_data() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "never instructions" in lower or "not instructions" in lower


def test_prompt_distinguishes_not_logged_from_absent() -> None:
    assert "not logged" in SYSTEM_PROMPT.lower()


def test_prompt_glossary_uses_the_bots_russian_metric_names() -> None:
    assert "настроение" in SYSTEM_PROMPT.lower()
    assert "тревога" in SYSTEM_PROMPT.lower()


def test_prompt_has_crisis_guidance() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "harm" in lower
    assert "emergency" in lower or "crisis line" in lower
