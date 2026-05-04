"""HELP_TEXT must list every registered command and explain when to use it.

Goals:
- Every Command(...) handler the bot registers shows up in HELP_TEXT.
- Each command line carries a use-case framing ("Use ..." or
  equivalent) so a new user knows when to reach for it — not just
  what the command does.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.bot.handlers.quick import QUICK_COMMANDS
from app.bot.handlers.start import HELP_TEXT

HANDLER_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "handlers"


def _registered_commands() -> set[str]:
    """Scrape Command("foo") usage across all handler modules."""
    found: set[str] = set()
    pattern = re.compile(r'Command\(["\']([a-z_]+)["\']\)')
    for py in HANDLER_DIR.glob("*.py"):
        for m in pattern.finditer(py.read_text(encoding="utf-8")):
            found.add(m.group(1))
    # Quick scale commands are registered in a loop, not by literal Command("x").
    found.update(QUICK_COMMANDS.keys())
    # /start is registered with CommandStart() — track it explicitly.
    found.add("start")
    return found


def test_help_text_mentions_every_registered_command() -> None:
    missing = sorted(c for c in _registered_commands() if f"/{c}" not in HELP_TEXT)
    assert not missing, f"HELP_TEXT is missing these commands: {missing}"


def test_help_text_includes_use_case_framing() -> None:
    """A reader should be able to learn WHEN to use commands, not just WHAT.

    Use-case framing is signalled by phrases like 'Use when', 'Use to',
    'Use for', 'Use right after', etc. We require a generous handful so
    the help is informative across multiple sections, not just decorated
    in one place.
    """
    occurrences = len(re.findall(r"\bUse\b (?:when|to|for|right|once|after)", HELP_TEXT))
    assert occurrences >= 8, (
        f"Expected several 'Use ...' use-case phrases across HELP_TEXT, "
        f"got {occurrences}. HELP_TEXT should explain when to reach for "
        f"each command, not just list them."
    )


def test_help_text_groups_remain_present() -> None:
    """Sections survive the rewrite so the help stays scannable."""
    for header in ("Logging", "Behavioral activation", "Review", "Auto summaries", "Settings"):
        assert header in HELP_TEXT, f"Missing section header: {header!r}"
