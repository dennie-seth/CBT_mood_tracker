"""Persistent home keyboard (reply keyboard under the text field).

Button presses arrive as plain text messages, so every label must map back
to an action in either language (`resolve_home_button`). The two metric
shortcuts are the user's most-logged quick metrics — computed from entries
they already have, nothing extra is stored.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.bot.i18n import SUPPORTED, t
from app.domain.enums import MetricType
from app.services.entry_service import EntryDTO

METRIC_EMOJI: dict[MetricType, str] = {
    MetricType.MOOD: "😊",
    MetricType.ENERGY: "⚡",
    MetricType.HUNGER: "🍽",
    MetricType.ANXIETY: "😰",
    MetricType.STRESS: "😣",
    MetricType.IRRITABILITY: "😤",
    MetricType.FOCUS: "🎯",
    MetricType.PAIN: "🩹",
    MetricType.SLEEP_QUALITY: "😴",
}
DEFAULT_METRICS: tuple[MetricType, ...] = (MetricType.MOOD, MetricType.ANXIETY)
_FIXED: tuple[str, ...] = ("migraine", "note", "today", "ask")


@dataclass(frozen=True, slots=True)
class HomeAction:
    kind: str  # metric | note | migraine | today | ask
    metric: MetricType | None = None


def metric_button(metric: MetricType, lang: str) -> str:
    return f"{METRIC_EMOJI[metric]} {t(lang, f'short.{metric.value}')}"


def top_quick_metrics(rows: Iterable[EntryDTO], n: int = 2) -> list[MetricType]:
    counts = Counter(r.metric_type for r in rows if r.metric_type in METRIC_EMOJI)
    top = [m for m, _ in counts.most_common(n)]
    for m in DEFAULT_METRICS:
        if len(top) >= n:
            break
        if m not in top:
            top.append(m)
    return top[:n]


def home_keyboard(lang: str, metrics: list[MetricType]) -> ReplyKeyboardMarkup:
    row1 = [KeyboardButton(text=metric_button(m, lang)) for m in metrics]
    row1.append(KeyboardButton(text=t(lang, "home.migraine")))
    row2 = [KeyboardButton(text=t(lang, f"home.{k}")) for k in ("note", "today", "ask")]
    return ReplyKeyboardMarkup(
        keyboard=[row1, row2], resize_keyboard=True, is_persistent=True
    )


def _build_lookup() -> dict[str, HomeAction]:
    lookup: dict[str, HomeAction] = {}
    for lang in SUPPORTED:
        for m in METRIC_EMOJI:
            lookup[metric_button(m, lang)] = HomeAction("metric", m)
        for kind in _FIXED:
            lookup[t(lang, f"home.{kind}")] = HomeAction(kind)
    return lookup


_LOOKUP = _build_lookup()


def resolve_home_button(text: str | None) -> HomeAction | None:
    return _LOOKUP.get(text or "")
