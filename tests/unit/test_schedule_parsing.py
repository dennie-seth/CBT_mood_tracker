from __future__ import annotations

from datetime import time

import pytest

from app.services.schedule_service import parse_time, parse_weekday


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("21:00", time(21, 0)),
        ("0:0", time(0, 0)),
        ("9:05", time(9, 5)),
        ("23:59", time(23, 59)),
    ],
)
def test_parse_time_happy(raw: str, expected: time) -> None:
    assert parse_time(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "21", "21:60", "24:00", "abc", "21:00:00", "-1:00"],
)
def test_parse_time_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_time(raw)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("mon", 0),
        ("MON", 0),
        ("Tue", 1),
        ("wed", 2),
        ("thu", 3),
        ("fri", 4),
        ("sat", 5),
        ("sun", 6),
    ],
)
def test_parse_weekday_happy(raw: str, expected: int) -> None:
    assert parse_weekday(raw) == expected


@pytest.mark.parametrize("raw", ["", "monday", "tues", "0", "7", "xyz"])
def test_parse_weekday_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_weekday(raw)
