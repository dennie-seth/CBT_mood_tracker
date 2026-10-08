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
