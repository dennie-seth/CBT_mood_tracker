"""User-message prompts driven by SummaryService into AiService.answer.

Kept short — the rich behaviour (tone, safety, tool guidance) is already
in app/ai/prompts.py:SYSTEM_PROMPT.
"""
from __future__ import annotations


DAILY_PROMPT = (
    "Generate today's CBT-tracker summary for me. "
    "(1) Pull today's entries via the `query_entries` tool. "
    "(2) Summarise mood, energy, sleep and any other tracked metrics in at most "
    "four short bullet points, focusing on the day's dynamics. "
    "(3) Add ONE supportive tip grounded in what you saw. "
    "(4) If today has no entries at all, send a brief, warm acknowledgement and "
    "a single low-effort reflection prompt — do not lecture. "
    "(5) Also call `query_entries` with metric_types=['activity_plan'] over the "
    "last 14 days. If any have extra.status == 'scheduled' and "
    "extra.planned_for <= today (user's tz), mention them in ONE sentence "
    "(e.g. 'You have N pending plan(s) for today: …'). Don't lecture, don't "
    "repeat if there are none. "
    "Reply in the user's language as inferred from recent entries; default to English. "
    "Keep it under ~140 words."
)


WEEKLY_PROMPT = (
    "Generate this week's CBT-tracker summary for me. "
    "(1) Use the `daily_summary` tool for the past 7 days. "
    "(2) Highlight ONE trend that's improving and ONE that's worsening or noisy, "
    "in plain language. "
    "(3) Suggest a single, concrete focus area for next week. "
    "(4) Optionally call `generate_chart` once with mood + energy + anxiety so "
    "the user sees the picture. "
    "Reply in the user's language as inferred from recent entries; default to English. "
    "Keep it under ~150 words."
)
