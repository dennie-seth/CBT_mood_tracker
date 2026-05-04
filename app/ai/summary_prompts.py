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
    "Reply in the user's language as inferred from recent entries; default to English. "
    "Keep it under ~120 words."
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
