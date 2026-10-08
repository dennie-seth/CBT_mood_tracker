"""Grader self-test (oracle + null), run before any paid eval pass.

Oracle: hand-written correct answers must pass everything.
Null: empty, "I don't know", and a confident answer to a different question
must fail. Also checks the programmatic format/language rules offline.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytz

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(1, str(HERE))

from cases import CASES  # noqa: E402
from fixture import TZ, build  # noqa: E402
from judge import judge, language_ok, plain_text_ok  # noqa: E402
from memory_repo import MemoryEntryRepo  # noqa: E402
from run_eval import _check_harness, _load_api_key  # noqa: E402

ORACLE = {
    "not_logged_anxiety": (
        "You didn't log anxiety on {wd3} {d3}, so I can't say how anxious you were. That day you "
        "logged a migraine at 11:30 (intensity 6), 7.5 h of sleep and mood 6 twice."
    ),
    "seq_trap_argument": (
        "On {wd6} {d6} you logged anxiety 8 at 10:00, and the note about the argument with your "
        "sister came later, at 16:00. So in your log the anxiety came first — it doesn't show the "
        "argument setting it off, though the argument may have happened before you wrote it down. "
        "By 21:05 your anxiety was 5."
    ),
    "ru_last_migraine": (
        "Последняя мигрень началась {d3} ({wd3}) в 11:30, сила 6. Когда она закончилась, ты не "
        "отметила, так что длительность неизвестна."
    ),
    "ba_rating": (
        "It helped more than you expected: you thought the walk by the river would help 3/10, and "
        "afterwards you rated it 8/10."
    ),
}
WRONG_QUESTION = "Your average sleep over the past seven days was 6.8 hours, with the shortest night on {wd2}."


async def main() -> None:
    assert plain_text_ok("• one\n• two") and not plain_text_ok("**bold**")
    assert not plain_text_ok("# Heading\ntext") and not plain_text_ok("use `code`")
    assert not plain_text_ok("") and plain_text_ok("Mood 6 - fine.")
    assert language_ok("Как прошла неделя? Настроение 6.", "ru")
    assert not language_ok("Your mood was 6.", "ru") and language_ok("Your mood was 6.", "en")
    print("programmatic checks: ok")

    _check_harness(approve=False)
    from anthropic import AsyncAnthropic
    from cryptography.fernet import Fernet

    from app.domain.models import User
    from app.infrastructure.crypto import FernetCipher
    from app.services.entry_service import EntryService
    from app.services.migraine_service import MigraineService

    client = AsyncAnthropic(api_key=_load_api_key(HERE.parents[1] / ".env"), max_retries=4)
    today = datetime.now(tz=pytz.timezone(TZ)).date()
    user = User(telegram_id=1, display_name="eval", timezone=TZ, language="en")
    user.id = 1
    fx = await build(EntryService(MemoryEntryRepo(), FernetCipher([Fernet.generate_key().decode()])),
                     MigraineService, user, today)
    by_id = {c.id: c for c in CASES}

    async def grade(case_id: str, answer: str) -> tuple[int, int, list[str]]:
        case = by_id[case_id]
        q, checks = case.render(fx.facts)
        j = await judge(client, journal=fx.lines, today=f"{fx.facts['today_wd']} {today}",
                        question=q, lang=case.lang, checks=checks, answer=answer)
        return sum(j.passes), len(checks), j.reasons

    jobs = []
    for cid, tmpl in ORACLE.items():
        jobs.append(("oracle", cid, tmpl.format(**fx.facts)))
        jobs.append(("null-empty", cid, ""))
        jobs.append(("null-idk", cid, "I don't know."))
        jobs.append(("null-wrong-q", cid, WRONG_QUESTION.format(**fx.facts)))
    results = await asyncio.gather(*(grade(cid, ans) for _, cid, ans in jobs))
    ok = True
    for (kind, cid, _), (passed, total, reasons) in zip(jobs, results, strict=True):
        expect_all = kind == "oracle"
        good = passed == total if expect_all else passed < total
        ok &= good
        print(f"{'OK ' if good else 'BAD'} {kind:13} {cid:20} {passed}/{total}")
        if not good:
            for r in reasons:
                print(f"      - {r}")
    print("grader self-test:", "PASSED" if ok else "FAILED")


asyncio.run(main())
