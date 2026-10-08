"""One-message logging: 'mood 6 anxiety 7 slept 6.5' / 'настроение 4 сон 7ч'.

Pure, local parsing — no AI sees the text. Deliberately strict: the whole
message must be metric/value pairs, otherwise it's treated as free text.
"""
from __future__ import annotations

import re

from app.domain.enums import MetricType

_SCALE_ALIASES: dict[str, MetricType] = {
    "mood": MetricType.MOOD, "настроение": MetricType.MOOD, "настр": MetricType.MOOD,
    "energy": MetricType.ENERGY, "энергия": MetricType.ENERGY,
    "hunger": MetricType.HUNGER, "appetite": MetricType.HUNGER,
    "голод": MetricType.HUNGER, "аппетит": MetricType.HUNGER,
    "anxiety": MetricType.ANXIETY, "тревога": MetricType.ANXIETY,
    "stress": MetricType.STRESS, "стресс": MetricType.STRESS,
    "irritability": MetricType.IRRITABILITY, "раздражение": MetricType.IRRITABILITY,
    "раздражительность": MetricType.IRRITABILITY,
    "focus": MetricType.FOCUS, "фокус": MetricType.FOCUS,
    "концентрация": MetricType.FOCUS,
    "pain": MetricType.PAIN, "боль": MetricType.PAIN,
    # Plain "sleep"/"сон" = quality, matching the /sleep command; an "h"/"ч"
    # suffix turns it into hours.
    "sleep": MetricType.SLEEP_QUALITY, "сон": MetricType.SLEEP_QUALITY,
}
_HOURS_ALIASES: frozenset[str] = frozenset({"slept", "sleephours", "спала", "спал"})

_PAIR_RE = re.compile(
    r"\s*([^\W\d_]+)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(h|ч)?\s*[,;]?\s*",
    re.IGNORECASE,
)


def parse_quick_log(text: str) -> list[tuple[MetricType, float]] | None:
    """Return [(metric, value), …] or None if this isn't a pure quick log."""
    if not text or not text.strip():
        return None
    out: list[tuple[MetricType, float]] = []
    pos = 0
    while pos < len(text):
        m = _PAIR_RE.match(text, pos)
        if not m or m.end() == pos:
            return None
        word = m.group(1).lower()
        value = float(m.group(2).replace(",", "."))
        hours = bool(m.group(3))
        if word in _HOURS_ALIASES or (hours and word in ("sleep", "сон")):
            metric = MetricType.SLEEP_HOURS
            if not 0 <= value <= 24:
                return None
        elif word in _SCALE_ALIASES and not hours:
            metric = _SCALE_ALIASES[word]
            if not 0 <= value <= 10:
                return None
        else:
            return None
        if any(existing is metric for existing, _ in out):
            return None  # "mood 6 mood 7" — which one?
        out.append((metric, value))
        pos = m.end()
    return out or None
