from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.enums import METRIC_LABELS, NUMERIC_METRICS, TEXT_METRICS, MetricType


def scale_1_to_10(callback_prefix: str) -> InlineKeyboardMarkup:
    """Inline keyboard with two rows of buttons 1..10."""
    rows = [
        [
            InlineKeyboardButton(text=str(i), callback_data=f"{callback_prefix}:{i}")
            for i in range(1, 6)
        ],
        [
            InlineKeyboardButton(text=str(i), callback_data=f"{callback_prefix}:{i}")
            for i in range(6, 11)
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def metric_picker(callback_prefix: str = "metric") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    numeric_sorted = sorted(NUMERIC_METRICS, key=lambda m: m.value)
    text_sorted = sorted(TEXT_METRICS, key=lambda m: m.value)

    def chunk(items: list[MetricType], size: int = 2) -> list[list[InlineKeyboardButton]]:
        out: list[list[InlineKeyboardButton]] = []
        for i in range(0, len(items), size):
            out.append(
                [
                    InlineKeyboardButton(
                        text=METRIC_LABELS[m],
                        callback_data=f"{callback_prefix}:{m.value}",
                    )
                    for m in items[i : i + size]
                ]
            )
        return out

    rows.extend(chunk(numeric_sorted))
    rows.extend(chunk(text_sorted))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def period_picker(callback_prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="7d", callback_data=f"{callback_prefix}:7d"),
                InlineKeyboardButton(text="30d", callback_data=f"{callback_prefix}:30d"),
                InlineKeyboardButton(text="90d", callback_data=f"{callback_prefix}:90d"),
                InlineKeyboardButton(text="all", callback_data=f"{callback_prefix}:all"),
            ]
        ]
    )
