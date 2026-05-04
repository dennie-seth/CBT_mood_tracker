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
