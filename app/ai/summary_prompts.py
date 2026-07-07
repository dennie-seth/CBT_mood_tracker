"""User-message prompts driven by SummaryService into AiService.answer.

Kept short — the rich behaviour (tone, safety, tool guidance) is already
in app/ai/prompts.py:SYSTEM_PROMPT.
"""
from __future__ import annotations

DAILY_PROMPT = (
    "Generate today's CBT-tracker summary for me. "
    "(1) Pull today's entries via the `query_entries` tool; read them in the "
    "order they were logged (use the local times) so the day's sequence is right. "
    "(2) Summarise mood, energy, sleep and any other tracked metrics in at most "
    "four short bullet points, focusing on the day's dynamics — and, where the "
    "timing makes it clear, what a note or event seemed to shift. "
    "(3) Add ONE supportive tip grounded in what you saw. "
    "(4) If today has no entries at all, send a brief, warm acknowledgement and "
    "a single low-effort reflection prompt — do not lecture. "
    "(5) Also call `query_entries` with metric_types=['activity_plan'] over the "
    "last 14 days. If any have extra.status == 'scheduled' and "
    "extra.planned_for <= today (user's tz), mention them in ONE sentence "
    "(e.g. 'You have N pending plan(s) for today: …'). Don't lecture, don't "
    "repeat if there are none. "
    "Keep it under ~150 words."
)


WEEKLY_PROMPT = (
    "Generate this week's CBT-tracker summary for me. "
    "(1) Call `daily_summary` for the past 7 days to see the numeric trends. "
    "(2) Also call `query_entries` for the past 7 days with "
    "metric_types=['thought_record','trigger','activity','coping','substance',"
    "'symptom','note'] to see what actually happened; use the local timestamps "
    "to keep events in order. "
    "(3) Connect events to numbers: name the 1-2 clearest cause→effect links you "
    "can actually see in the data, citing the day (e.g. 'after <event> on Tue, "
    "mood dropped 7→4 the next morning'). If nothing is clear, say so instead of "
    "guessing. "
    "(4) Call out ONE trend improving and ONE worsening or noisy, in plain "
    "language, interpreting the scales correctly (higher mood/energy/focus = "
    "better; higher anxiety/stress/pain = worse). "
    "(5) Suggest a single concrete focus for next week grounded in the above. "
    "(6) Optionally call `generate_chart` once with mood + energy + anxiety so "
    "the user sees the picture. "
    "Keep it under ~200 words."
)
