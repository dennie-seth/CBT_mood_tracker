from __future__ import annotations

from datetime import date

import pytest

from app.services.time import parse_period


def test_parse_7d() -> None:
    start, end = parse_period("7d", "UTC")
    assert (end - start).days == 6


def test_parse_30d() -> None:
    start, end = parse_period("30d", "UTC")
    assert (end - start).days == 29


def test_parse_all() -> None:
    start, end = parse_period("all", "UTC")
    assert start == date(1970, 1, 1)
    assert end >= start


def test_invalid_period() -> None:
    with pytest.raises(ValueError):
        parse_period("forever", "UTC")


def test_zero_days_rejected() -> None:
    with pytest.raises(ValueError):
        parse_period("0d", "UTC")
