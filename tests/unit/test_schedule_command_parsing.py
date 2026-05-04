from __future__ import annotations

from datetime import time

import pytest

from app.services.schedule_service import parse_weekly_args


def test_parse_weekly_args_happy() -> None:
    assert parse_weekly_args("sun 21:00") == (6, time(21, 0))
    assert parse_weekly_args("MON 09:30") == (0, time(9, 30))
    # extra whitespace tolerated
    assert parse_weekly_args("  sat   7:5  ") == (5, time(7, 5))


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "sun",
        "21:00",
        "sunday 21:00",
        "sun 25:00",
        "sun 21:00 extra",
    ],
)
def test_parse_weekly_args_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_weekly_args(raw)
