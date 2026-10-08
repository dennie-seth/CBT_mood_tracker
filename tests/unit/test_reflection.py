"""Year-in-pixels image and /export csv."""
from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest
from aiogram.types import Message

from app.bot.handlers import chart, export
from app.domain.enums import MetricType
from app.domain.models import User
from app.services.chart_service import ChartService
from app.services.csv_export_service import CsvExportService
from app.services.entry_service import EntryService
from tests.unit.fakes import FakeEntryRepo


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="t", timezone="Europe/Berlin", language="en")
    u.id = 42
    return u


@pytest.fixture()
def repo() -> FakeEntryRepo:
    return FakeEntryRepo()


@pytest.fixture()
def es(repo, cipher) -> EntryService:
    return EntryService(repo, cipher)


def _rows(data: bytes) -> list[list[str]]:
    assert data.startswith(b"\xef\xbb\xbf")  # BOM so Excel opens Cyrillic correctly
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))


# --- CSV ---------------------------------------------------------------------

async def test_csv_has_decrypted_rows_in_local_time(es, user) -> None:
    at = datetime(2026, 10, 1, 21, 30, tzinfo=UTC)  # 23:30 in Berlin
    await es.create(user, MetricType.MOOD, value_numeric=6, recorded_at=at)
    await es.create(user, MetricType.NOTE, value_text='line one\nline "two", with comma', recorded_at=at)
    await es.create(user, MetricType.THOUGHT_RECORD, recorded_at=at,
                    extra={"situation_text": "meeting", "reframe_text": "it was fine"})

    rows = _rows(await CsvExportService(es).export(user, date(2026, 9, 1), date(2026, 10, 8)))

    assert rows[0] == ["date", "time", "metric", "value", "text", "details"]
    assert rows[1][:4] == ["2026-10-01", "23:30", "mood", "6"]
    assert rows[2][4] == 'line one\nline "two", with comma'
    details = json.loads(rows[3][5])
    assert details == {"situation_text": "meeting", "reframe_text": "it was fine"}


async def test_csv_only_own_entries(es, user) -> None:
    other = User(telegram_id=2, display_name="o", timezone="UTC")
    other.id = 99
    await es.create(other, MetricType.NOTE, value_text="not yours")
    rows = _rows(await CsvExportService(es).export(user, date(2020, 1, 1), date(2030, 1, 1)))
    assert rows == [["date", "time", "metric", "value", "text", "details"]]


# --- year in pixels ------------------------------------------------------------

def _year_df(days: dict[str, dict[str, float]]) -> pd.DataFrame:
    df = pd.DataFrame.from_dict(days, orient="index")
    df.index = pd.to_datetime(df.index)
    return df


def test_year_pixels_renders_png_with_migraine_marks(monkeypatch) -> None:
    import matplotlib.axes

    glyphs: list[str] = []
    real_text = matplotlib.axes.Axes.text

    def text(self, x, y, s, *a, **kw):
        glyphs.append(s)
        return real_text(self, x, y, s, *a, **kw)

    monkeypatch.setattr(matplotlib.axes.Axes, "text", text)
    df = _year_df({
        "2026-01-05": {"mood": 3.0},
        "2026-03-10": {"mood": 8.0, "migraine": 7.0},
        "2026-07-04": {"migraine": 5.0},  # attack logged, no mood
    })
    png = ChartService().year_pixels(df, year=2026)
    assert png.startswith(b"\x89PNG")
    assert glyphs.count("▼") == 2


def test_year_pixels_empty_is_placeholder() -> None:
    png = ChartService().year_pixels(pd.DataFrame(), year=2026)
    assert png.startswith(b"\x89PNG")
    assert len(png) < len(ChartService().year_pixels(_year_df({"2026-01-05": {"mood": 3.0}}), year=2026))


# --- handlers ------------------------------------------------------------------

def _msg(text: str) -> MagicMock:
    m = MagicMock(spec=Message)
    m.text = text
    m.chat = MagicMock(id=1)
    m.answer = AsyncMock()
    m.answer_photo = AsyncMock()
    m.answer_document = AsyncMock()
    return m


async def test_pixels_command(user, monkeypatch) -> None:
    daily = AsyncMock(return_value=_year_df({"2026-03-10": {"mood": 8.0, "migraine": 6.0}}))
    monkeypatch.setattr(chart, "_daily_summary", daily)
    m = _msg("/pixels 2026")
    await chart.cmd_pixels(m, MagicMock(args="2026"), user, None, MagicMock(chart_service=ChartService()))
    start, end = daily.await_args.args[2:4]
    assert (start, end) == (date(2026, 1, 1), date(2026, 12, 31))
    caption = m.answer_photo.await_args.kwargs["caption"]
    assert "2026" in caption and "1" in caption


async def test_pixels_rejects_bad_year(user) -> None:
    m = _msg("/pixels 1890")
    await chart.cmd_pixels(m, MagicMock(args="1890"), user, None, MagicMock())
    m.answer_photo.assert_not_awaited()
    m.answer.assert_awaited()


async def test_export_csv(user, repo, es, cipher, monkeypatch) -> None:
    monkeypatch.setattr(export, "entry_service", lambda s, c: EntryService(repo, cipher))
    await es.create(user, MetricType.MOOD, value_numeric=5)
    m = _msg("/export csv 30d")
    bot = AsyncMock()
    m.bot = bot
    await export.cmd_export(m, MagicMock(args="csv 30d"), user, None, MagicMock(cipher=cipher))
    doc = bot.send_document.await_args.args[1]
    assert doc.filename.endswith(".csv")
    assert _rows(doc.data)[1][2] == "mood"
