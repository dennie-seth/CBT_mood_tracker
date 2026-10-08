"""Telegram command menu + the persistent home keyboard.

- Every menu entry is a real registered command, described in EN and RU,
  within Telegram's limits.
- Home keyboard: the two metric shortcuts are the user's most-logged quick
  metrics (from existing entries — nothing new stored); every button text
  in either language resolves to an action.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.bot.commands import MENU, menu_commands
from app.bot.home import (
    HomeAction,
    home_keyboard,
    resolve_home_button,
    top_quick_metrics,
)
from app.bot.i18n import EN, RU
from app.domain.enums import MetricType
from app.services.entry_service import EntryDTO

HANDLER_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "handlers"


def _registered() -> set[str]:
    from app.bot.handlers.quick import QUICK_COMMANDS

    found = {"start"} | set(QUICK_COMMANDS)
    pattern = re.compile(r'Command\(["\']([a-z_]+)["\']\)')
    for py in HANDLER_DIR.glob("*.py"):
        found |= set(pattern.findall(py.read_text(encoding="utf-8")))
    return found


def test_menu_entries_are_registered_commands() -> None:
    missing = [c for c in MENU if c not in _registered()]
    assert not missing, missing


@pytest.mark.parametrize("lang", ["en", "ru"])
def test_menu_descriptions_exist_and_fit(lang) -> None:
    table = EN if lang == "en" else RU
    cmds = menu_commands(lang)
    assert [c.command for c in cmds] == list(MENU)
    for c in cmds:
        assert f"cmd.{c.command}" in table, f"{lang}: cmd.{c.command}"
        assert 3 <= len(c.description) <= 256
        assert re.fullmatch(r"[a-z0-9_]{1,32}", c.command)
    assert len(cmds) <= 100


def _dto(metric: MetricType) -> EntryDTO:
    return EntryDTO(
        id=1, recorded_at=datetime(2026, 10, 1, tzinfo=UTC), entry_date=date(2026, 10, 1),
        metric_type=metric, value_numeric=5.0, value_text=None, tags=None, extra=None,
    )


def test_top_quick_metrics_by_usage() -> None:
    rows = [_dto(MetricType.ANXIETY)] * 5 + [_dto(MetricType.SLEEP_QUALITY)] * 3 \
        + [_dto(MetricType.MOOD)] * 2 + [_dto(MetricType.NOTE)] * 9
    assert top_quick_metrics(rows) == [MetricType.ANXIETY, MetricType.SLEEP_QUALITY]


def test_top_quick_metrics_defaults_and_fills() -> None:
    assert top_quick_metrics([]) == [MetricType.MOOD, MetricType.ANXIETY]
    assert top_quick_metrics([_dto(MetricType.STRESS)]) == [MetricType.STRESS, MetricType.MOOD]


@pytest.mark.parametrize("lang", ["en", "ru"])
def test_every_home_button_resolves(lang) -> None:
    kb = home_keyboard(lang, [MetricType.ANXIETY, MetricType.FOCUS])
    assert kb.is_persistent and kb.resize_keyboard
    texts = [b.text for row in kb.keyboard for b in row]
    actions = [resolve_home_button(t) for t in texts]
    assert None not in actions
    assert HomeAction("metric", MetricType.ANXIETY) in actions
    assert HomeAction("metric", MetricType.FOCUS) in actions
    for kind in ("note", "migraine", "today", "ask"):
        assert HomeAction(kind) in actions


def test_unrelated_text_is_not_a_button() -> None:
    assert resolve_home_button("Mood") is None  # needs the exact label
    assert resolve_home_button("hello") is None
