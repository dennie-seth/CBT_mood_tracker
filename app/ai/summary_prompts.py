"""User-message prompts driven by SummaryService into AiService.answer.

Kept short — the rich behaviour (tone, safety, tool guidance) is already
in app/ai/prompts.py:SYSTEM_PROMPT.
"""
from __future__ import annotations

from datetime import date

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
    "If prior weekly summaries are shown above, treat them as your memory of "
    "recent weeks: don't restate the data blindly — build on them. Note what "
    "carried over from last week, what changed, and whether the focus you "
    "suggested then actually seems to have helped, citing the specific thing. "
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


def build_weekly_context(priors: list[tuple[date, date, str]]) -> str:
    """Render prior weekly summaries as a continuity preamble for WEEKLY_PROMPT.

    `priors` is ``(week_start, week_end, text)`` in chronological order
    (oldest first). Returns an empty string when there are none, so the very
    first week's prompt is unchanged. Deterministic — no AI call — so the
    continuity context is free and reproducible.
    """
    if not priors:
        return ""
    lines = [
        "Here are your most recent weekly summaries (oldest first), as memory "
        "of what has been happening. Build on them in the summary below:"
    ]
    for week_start, week_end, text in priors:
        lines.append(
            f"\n[week {week_start.isoformat()} to {week_end.isoformat()}]\n{text.strip()}"
        )
    return "\n".join(lines)

