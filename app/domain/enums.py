from __future__ import annotations

from enum import StrEnum


class MetricType(StrEnum):
    # Quantitative scales (1-10 unless noted)
    SLEEP_HOURS = "sleep_hours"
    SLEEP_QUALITY = "sleep_quality"
    MOOD = "mood"
    ENERGY = "energy"
    HUNGER = "hunger"
    ANXIETY = "anxiety"
    STRESS = "stress"
    IRRITABILITY = "irritability"
    FOCUS = "focus"
    PAIN = "pain"

    # Qualitative (free text, encrypted)
    SYMPTOM = "symptom"
    THOUGHT_RECORD = "thought_record"
    ACTIVITY = "activity"
    ACTIVITY_PLAN = "activity_plan"
    SUBSTANCE = "substance"
    TRIGGER = "trigger"
    COPING = "coping"
    NOTE = "note"


NUMERIC_METRICS: frozenset[MetricType] = frozenset(
    {
        MetricType.SLEEP_HOURS,
        MetricType.SLEEP_QUALITY,
        MetricType.MOOD,
        MetricType.ENERGY,
        MetricType.HUNGER,
        MetricType.ANXIETY,
        MetricType.STRESS,
        MetricType.IRRITABILITY,
        MetricType.FOCUS,
        MetricType.PAIN,
    }
)

TEXT_METRICS: frozenset[MetricType] = frozenset(
    {
        MetricType.SYMPTOM,
        MetricType.THOUGHT_RECORD,
        MetricType.ACTIVITY,
        MetricType.ACTIVITY_PLAN,
        MetricType.SUBSTANCE,
        MetricType.TRIGGER,
        MetricType.COPING,
        MetricType.NOTE,
    }
)


METRIC_LABELS: dict[MetricType, str] = {
    MetricType.SLEEP_HOURS: "Sleep duration (hours)",
    MetricType.SLEEP_QUALITY: "Sleep quality (1-10)",
    MetricType.MOOD: "Mood (1-10)",
    MetricType.ENERGY: "Energy (1-10)",
    MetricType.HUNGER: "Hunger / appetite (1-10)",
    MetricType.ANXIETY: "Anxiety (1-10)",
    MetricType.STRESS: "Stress (1-10)",
    MetricType.IRRITABILITY: "Irritability (1-10)",
    MetricType.FOCUS: "Focus (1-10)",
    MetricType.PAIN: "Body pain (1-10)",
    MetricType.SYMPTOM: "Body symptom",
    MetricType.THOUGHT_RECORD: "Thought record",
    MetricType.ACTIVITY: "Activity",
    MetricType.ACTIVITY_PLAN: "Behavioral activation plan",
    MetricType.SUBSTANCE: "Substance / medication",
    MetricType.TRIGGER: "Trigger",
    MetricType.COPING: "Coping strategy",
    MetricType.NOTE: "Free-form note",
}


# Scale semantics so the assistant interprets numeric values consistently.
# Each line states the polarity (which direction is "good") and what low /
# mid / high roughly mean. Kept English — the domain stays language-agnostic;
# the AI reply language is handled separately in AiService.
METRIC_SEMANTICS: dict[MetricType, str] = {
    MetricType.SLEEP_HOURS: (
        "Hours of sleep (not a 1-10 scale). Healthy band is roughly 7-9h; "
        "both under ~6h and over ~10h are notable rather than 'good'."
    ),
    MetricType.SLEEP_QUALITY: (
        "Higher is better. 1-3 = poor/restless, 4-6 = okay, 7-10 = restful."
    ),
    MetricType.MOOD: (
        "Higher is better. 1-3 = low/down, 4-6 = neutral, 7-10 = good/positive."
    ),
    MetricType.ENERGY: (
        "Higher is better. 1-3 = depleted, 4-6 = moderate, 7-10 = energetic."
    ),
    MetricType.HUNGER: (
        "Appetite level — not good or bad in itself. 1-3 = little appetite, "
        "4-6 = normal, 7-10 = strong appetite. Extremes are the signal."
    ),
    MetricType.ANXIETY: (
        "Higher is worse. 1-3 = calm, 4-6 = moderate, 7-10 = high/distressing."
    ),
    MetricType.STRESS: (
        "Higher is worse. 1-3 = relaxed, 4-6 = moderate, 7-10 = overwhelmed."
    ),
    MetricType.IRRITABILITY: (
        "Higher is worse. 1-3 = even-tempered, 4-6 = moderate, 7-10 = very irritable."
    ),
    MetricType.FOCUS: (
        "Higher is better. 1-3 = scattered, 4-6 = okay, 7-10 = sharp."
    ),
    MetricType.PAIN: (
        "Higher is worse. 0-1 = none, 2-4 = mild, 5-7 = moderate, 8-10 = severe."
    ),
}


def metric_semantics_block() -> str:
    """Render the numeric-scale semantics as a stable, prompt-ready block.

    Ordered by the ``MetricType`` definition order so the output is
    deterministic (handy for prompt caching and tests).
    """
    return "\n".join(
        f"- {METRIC_LABELS[m]}: {METRIC_SEMANTICS[m]}"
        for m in MetricType
        if m in NUMERIC_METRICS
    )
