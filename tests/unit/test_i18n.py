"""Tiny i18n: t(lang, key, **fmt) returns the localized string.

Rules:
- Known key + known lang → that translation, with str.format kwargs applied.
- Known key + unknown lang → English fallback.
- Unknown key → returns the key itself (loud signal, doesn't crash).
- Every key in RU must also exist in EN (no orphan translations).

Auto-detect: detect_language(language_code) → "ru" if code starts with
"ru" (e.g. "ru", "ru-RU"), else "en". `None` → "en".
"""
from __future__ import annotations

import pytest

from app.bot.i18n import EN, RU, detect_language, t


def test_t_returns_english_for_known_key() -> None:
    assert t("en", "cancel.done") == "Cancelled."


def test_t_returns_russian_for_known_key() -> None:
    # RU tracks the same keys.
    assert t("ru", "cancel.done") != "Cancelled."
    assert t("ru", "cancel.done") == RU["cancel.done"]


def test_t_falls_back_to_english_for_unknown_language() -> None:
    assert t("de", "cancel.done") == EN["cancel.done"]


def test_t_returns_key_itself_for_unknown_key() -> None:
    assert t("en", "definitely.not.a.real.key") == "definitely.not.a.real.key"


def test_t_supports_format_kwargs() -> None:
    # The key for the /start greeting accepts a name placeholder.
    assert "Pat" in t("en", "start.hi", name="Pat")
    assert "Pat" in t("ru", "start.hi", name="Pat")


def test_ru_has_no_orphan_keys() -> None:
    """Every RU translation must shadow an existing EN key.

    Prevents dead translations from drifting after rename/removal.
    """
    orphans = sorted(set(RU) - set(EN))
    assert orphans == [], f"RU has keys missing from EN: {orphans}"


@pytest.mark.parametrize(
    "code,expected",
    [
        ("ru", "ru"),
        ("ru-RU", "ru"),
        ("RU", "ru"),
        ("en", "en"),
        ("en-US", "en"),
        ("de", "en"),
        (None, "en"),
        ("", "en"),
    ],
)
def test_detect_language_picks_ru_for_russian_codes(code, expected) -> None:
    assert detect_language(code) == expected
