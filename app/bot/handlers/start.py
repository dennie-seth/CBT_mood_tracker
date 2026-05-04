from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.domain.models import User

router = Router()

HELP_TEXT = (
    "CBT tracker bot — log your day, ask Claude to analyse it.\n"
    "Each command below is followed by *when* to reach for it.\n\n"
    "📝 Logging\n"
    "/log — guided pick of any metric. Use when you want to log "
    "something less common (symptoms, focus, irritability) without "
    "remembering a specific command.\n"
    "/mood /sleep /energy /hunger /anxiety /stress /pain "
    "/irritability /focus — one-tap 1-10 scale. Use for fast "
    "in-the-moment captures (e.g. a sudden wave of anxiety).\n"
    "/sleephours — type sleep duration in hours (e.g. 7.5). "
    "Use right after waking to log how long you actually slept.\n"
    "/note <text> — free-form journal entry, encrypted at rest. "
    "Use when something is on your mind that doesn't fit any metric.\n"
    "/thought — guided CBT thought record (situation → automatic "
    "thought → distortion → reframe). Use when you catch a strong "
    "negative thought and want to work through it.\n"
    "/backfill <date> <metric> <value> — log for a past date. "
    "Use when you forgot to log yesterday or want to add an old entry.\n\n"
    "🌱 Behavioral activation\n"
    "/activate — plan a small mood-lifting activity and predict its "
    "lift. Use when you feel low and want a concrete step out of it.\n"
    "/plans — see open plans. Use to check what you've committed to.\n"
    "/done — mark a plan done and rate the actual lift. Use right "
    "after completing a planned activity — the predicted-vs-actual "
    "gap is the therapeutic insight.\n"
    "/skip — skip a plan with an optional reason. Use when something "
    "got in the way; no judgement.\n\n"
    "📊 Review\n"
    "/today — list today's entries. Use to see what you've logged so far.\n"
    "/week — last 7 days summary. Use for a quick weekly retrospective.\n"
    "/chart — pick a period and see a chart of numeric metrics. "
    "Use when you want to spot trends visually.\n"
    "/export — generate a multi-page PDF report (numeric only). "
    "Use for a private numeric snapshot or a personal archive.\n"
    "/therapist — richer PDF including thought records, BA outcomes, "
    "notes and other free-text. Use to share with a clinician — "
    "marked confidential, share only with people you trust.\n\n"
    "🤖 Claude\n"
    "/ask <question> — ask Claude anything about your data "
    "(e.g. 'what lifts my mood most?', 'when is my sleep worst?'). "
    "Use for analysis the bot's built-in views don't cover.\n\n"
    "⏰ Auto summaries (in your timezone)\n"
    "/schedule — show current daily / weekly auto-summary settings.\n"
    "/dailyat 21:00 — enable a daily Haiku summary at this time. "
    "Use to nudge yourself to reflect every evening.\n"
    "/dailyoff — disable the daily summary.\n"
    "/weeklyat sun 21:00 — enable a weekly Haiku summary on this "
    "day & time. Use for a Sunday-night week-in-review.\n"
    "/weeklyoff — disable the weekly summary.\n\n"
    "⚙️ Settings\n"
    "/tz <IANA> — set your timezone, e.g. /tz Europe/Berlin. "
    "Use once on first login; day boundaries depend on it.\n"
    "/cancel — abort the current guided step (any flow).\n"
    "/start, /help — show this list again."
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
