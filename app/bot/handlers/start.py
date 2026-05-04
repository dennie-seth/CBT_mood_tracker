from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.domain.models import User

router = Router()

HELP_TEXT = (
    "CBT tracker bot — log your day, ask Claude to analyse it.\n\n"
    "📝 Logging\n"
    "/log — guided entry (any metric)\n"
    "/mood /sleep /energy /hunger /anxiety /stress /pain — quick 1-10\n"
    "/note <text> — free-form journal\n"
    "/thought — guided CBT thought record\n"
    "/backfill <date> <metric> <value> — log for a past date\n\n"
    "🌱 Behavioral activation\n"
    "/activate — plan a small mood-lifting activity\n"
    "/plans — list open plans\n"
    "/done — mark a plan done and rate the actual lift\n"
    "/skip — skip a plan (with optional reason)\n\n"
    "📊 Review\n"
    "/today — today's entries\n"
    "/week — last 7 days summary\n"
    "/chart — pick a period and see a chart\n"
    "/export — generate a PDF report\n\n"
    "🤖 Claude\n"
    "/ask <question> — ask about your data\n\n"
    "⏰ Auto summaries (in your timezone)\n"
    "/schedule — show current daily / weekly settings\n"
    "/dailyat 21:00 — enable daily summary at this time\n"
    "/dailyoff — disable daily\n"
    "/weeklyat sun 21:00 — enable weekly summary on this day & time\n"
    "/weeklyoff — disable weekly\n\n"
    "⚙️ Settings\n"
    "/tz <IANA> — set your timezone (e.g. /tz Europe/Berlin)\n"
    "/cancel — abort the current step"
)


@router.message(CommandStart())
async def cmd_start(message: Message, user: User) -> None:
    name = user.display_name or "there"
    await message.answer(f"Hi {name}! You're all set.\n\n" + HELP_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state) -> None:  # type: ignore[no-untyped-def]
    await state.clear()
    await message.answer("Cancelled.")
