"""Splitter for /backfill command args.

Handles the awkward case that 'N days ago' is a 3-token date phrase.
"""
from __future__ import annotations

import pytest

from app.bot.handlers.backfill import split_backfill_args


def test_iso_date_three_tokens() -> None:
    assert split_backfill_args("2026-05-04 mood 7") == ("2026-05-04", "mood", "7")


def test_keyword_date_three_tokens() -> None:
    assert split_backfill_args("yesterday mood 7") == ("yesterday", "mood", "7")
    assert split_backfill_args("today note Felt good") == ("today", "note", "Felt good")


def test_n_days_ago_form() -> None:
    assert split_backfill_args("3 days ago mood 7") == ("3 days ago", "mood", "7")
    assert split_backfill_args("1 day ago mood 7") == ("1 day ago", "mood", "7")


def test_text_value_with_spaces() -> None:
    assert split_backfill_args("yesterday note Felt rough but the walk helped.") == (
        "yesterday",
        "note",
        "Felt rough but the walk helped.",
    )
    assert split_backfill_args("2 days ago symptom Headache + nausea after lunch") == (
        "2 days ago",
        "symptom",
        "Headache + nausea after lunch",
    )


def test_decimal_numeric() -> None:
    assert split_backfill_args("yesterday sleep_hours 7.5") == (
        "yesterday",
        "sleep_hours",
        "7.5",
    )


@pytest.mark.parametrize("raw", ["", "yesterday", "yesterday mood", "  "])
def test_too_few_tokens_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        split_backfill_args(raw)
