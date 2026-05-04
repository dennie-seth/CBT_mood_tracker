"""PdfService.therapist_report should:

- Return a non-empty bytes blob with a valid PDF magic header.
- Render thought records / BA outcomes / notes / other-text content even
  when the numeric daily_df is empty (a clinician's whole reason to look
  at this PDF could be the qualitative material).
- Drop sections gracefully when their list is empty (don't blow up on
  an all-empty payload — produce a "no data in range" cover and stop).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.domain.enums import MetricType
from app.domain.models import User
from app.services.pdf_service import PdfService
from app.services.therapist_export_service import (
    BAOutcome,
    TextEntry,
    TherapistReportData,
    ThoughtRecord,
)


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="Pat", timezone="UTC")
    u.id = 7
    return u


def test_therapist_report_returns_pdf_bytes_for_full_payload(user) -> None:
    df = pd.DataFrame(
        {"mood": [5.0, 6.0, 7.0]},
        index=pd.to_datetime(["2026-04-28", "2026-04-29", "2026-04-30"]),
    )
    data = TherapistReportData(
        daily_df=df,
        thought_records=[
            ThoughtRecord(
                entry_date=date(2026, 4, 29),
                situation="Big presentation",
                automatic_thought="I'll embarrass myself",
                distortion="fortune-telling",
                reframe="I've prepared; outcome uncertain, not catastrophic",
            )
        ],
        ba_outcomes=[
            BAOutcome(
                entry_date=date(2026, 4, 30),
                plan_text="walk in the park",
                status="done",
                predicted_effect=7,
                actual_effect=8,
                skip_reason=None,
            ),
            BAOutcome(
                entry_date=date(2026, 4, 28),
                plan_text="call brother",
                status="skipped",
                predicted_effect=5,
                actual_effect=None,
                skip_reason="low energy",
            ),
        ],
        notes=[TextEntry(date(2026, 4, 29), MetricType.NOTE, "Felt better after a walk")],
        other_text=[
            TextEntry(date(2026, 4, 28), MetricType.SYMPTOM, "headache, mild"),
            TextEntry(date(2026, 4, 30), MetricType.TRIGGER, "argument with manager"),
        ],
    )
    out = PdfService().therapist_report(
        data, user=user, start=date(2026, 4, 24), end=date(2026, 4, 30)
    )
    assert isinstance(out, bytes)
    assert out.startswith(b"%PDF")
    # Several pages of content should produce a non-trivial size.
    assert len(out) > 5_000


def test_therapist_report_handles_empty_payload(user) -> None:
    data = TherapistReportData(daily_df=pd.DataFrame())
    out = PdfService().therapist_report(
        data, user=user, start=date(2026, 4, 24), end=date(2026, 4, 30)
    )
    assert out.startswith(b"%PDF")
    assert len(out) > 1_000  # cover-page only is still a real PDF


def test_therapist_report_renders_qualitative_only_payload(user) -> None:
    """User had only thought records this week (no numeric logs)."""
    data = TherapistReportData(
        daily_df=pd.DataFrame(),
        thought_records=[
            ThoughtRecord(
                entry_date=date(2026, 4, 29),
                situation="Manager email",
                automatic_thought="They're going to fire me",
                distortion="catastrophising",
                reframe="It's a routine check-in",
            )
        ],
    )
    out = PdfService().therapist_report(
        data, user=user, start=date(2026, 4, 24), end=date(2026, 4, 30)
    )
    assert out.startswith(b"%PDF")
