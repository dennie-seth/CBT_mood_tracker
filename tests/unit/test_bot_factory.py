"""Regression tests for the Bot factory.

The bug we caught manually: setting `parse_mode=ParseMode.HTML` as the default
caused Telegram to reject any message containing literal `<text>` / `<question>`
placeholders in the help, since they look like unknown HTML tags. None of our
handlers actually emit HTML, so the fix is to leave the default unset.
"""
from __future__ import annotations

from app.bot.handlers.start import HELP_TEXT
from app.main import make_bot


def test_bot_has_no_default_parse_mode() -> None:
    bot = make_bot("123:fake-token")
    assert bot.default.parse_mode is None, (
        "Default parse_mode must stay unset — HELP_TEXT and other plain-text "
        "responses contain literal angle-bracket placeholders that would be "
        "mis-parsed as HTML/Markdown tags."
    )


def test_help_text_uses_angle_bracket_placeholders() -> None:
    """If we ever change to plain-text placeholders we can drop the parse_mode test."""
    assert "<text>" in HELP_TEXT
    assert "<question>" in HELP_TEXT
    assert "<IANA>" in HELP_TEXT
