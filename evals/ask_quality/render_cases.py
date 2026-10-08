"""Write cases.md: the fixture journal + every case, for human review."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytz

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from cases import CASES  # noqa: E402
from fixture import TZ, build  # noqa: E402
from memory_repo import MemoryEntryRepo  # noqa: E402


async def main() -> None:
    from cryptography.fernet import Fernet

    from app.domain.models import User
    from app.infrastructure.crypto import FernetCipher
    from app.services.entry_service import EntryService
    from app.services.migraine_service import MigraineService

    today = datetime.now(tz=pytz.timezone(TZ)).date()
    user = User(telegram_id=1, display_name="eval", timezone=TZ, language="en")
    user.id = 1
    es = EntryService(MemoryEntryRepo(), FernetCipher([Fernet.generate_key().decode()]))
    fx = await build(es, MigraineService, user, today)

    out = [f"# /ask eval — fictional journal and {len(CASES)} cases",
           "", f"Rendered for today = {fx.facts['today_wd']} {today} ({TZ}).", "",
           "| id | probes | lang | question |", "|---|---|---|---|"]
    for c in CASES:
        q, _ = c.render(fx.facts)
        out.append(f"| {c.id} | {c.tags[0]} | {c.lang} | {q} |")
    out += ["", "Every case is also checked programmatically: plain text (no Markdown) and "
            "reply language.", ""]
    for c in CASES:
        q, checks = c.render(fx.facts)
        out += [f"## {c.id}  ({c.tags[0]}, {c.lang})", "", "````text", q, "````", "", "Checks:"]
        out += [f"- {ch}" for ch in checks]
        if c.needs_tool:
            out.append(f"- (programmatic) the `{c.needs_tool}` tool was called")
        out.append("")
    out += ["## The fictional journal (what the grader treats as ground truth)", "", "````text",
            *fx.lines, "````", ""]
    (HERE / "cases.md").write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {HERE / 'cases.md'}: {len(CASES)} cases, {len(fx.lines)} journal lines")


asyncio.run(main())
