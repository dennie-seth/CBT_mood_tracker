from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.i18n import t
from app.domain.enums import METRIC_LABELS, NUMERIC_METRICS, TEXT_METRICS, MetricType
from app.services.migraine_service import SYMPTOMS


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


def plan_when_picker(callback_prefix: str = "plan_when") -> InlineKeyboardMarkup:
    """4-button date picker for /activate: today / tomorrow / +2 / +3 days.

    Callback data carries the offset in days, parsed by the handler against
    the user's local today.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="today", callback_data=f"{callback_prefix}:0"),
                InlineKeyboardButton(text="tomorrow", callback_data=f"{callback_prefix}:1"),
                InlineKeyboardButton(text="+2 days", callback_data=f"{callback_prefix}:2"),
                InlineKeyboardButton(text="+3 days", callback_data=f"{callback_prefix}:3"),
            ]
        ]
    )


def plan_picker(plans, callback_prefix: str) -> InlineKeyboardMarkup:
    """Inline list of open BA plans, one button per plan.

    Each button's text is "<weekday short> <date> — <truncated plan_text>";
    callback data is "<prefix>:<entry_id>". Callback data is capped at 64 bytes
    by Telegram, so the prefix should be short.
    """
    rows: list[list[InlineKeyboardButton]] = []
    for p in plans:
        plan_text = (p.extra or {}).get("plan_text", "(no description)")
        snippet = plan_text if len(plan_text) <= 32 else plan_text[:29] + "…"
        weekday = p.entry_date.strftime("%a")
        label = f"{weekday} {p.entry_date.isoformat()} — {snippet}"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"{callback_prefix}:{p.id}")]
        )
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


# --- /migraine ------------------------------------------------------------
# Labels are localized here (unlike the older pickers above) because these
# buttons carry whole words, not numbers.

MIGRAINE_HOURS_AGO: tuple[int, ...] = (1, 2, 4, 8)


def migraine_time_picker(lang: str, callback_prefix: str) -> InlineKeyboardMarkup:
    """Now / 1h / 2h / 4h / 8h ago. Callback data carries minutes ago."""
    ago = [
        InlineKeyboardButton(
            text=t(lang, "migraine.btn_ago", h=h),
            callback_data=f"{callback_prefix}:{h * 60}",
        )
        for h in MIGRAINE_HOURS_AGO
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "migraine.btn_now"), callback_data=f"{callback_prefix}:0")],
            ago,
        ]
    )


def migraine_yes_no(lang: str, callback_prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "migraine.btn_yes"), callback_data=f"{callback_prefix}:1"),
                InlineKeyboardButton(text=t(lang, "migraine.btn_no"), callback_data=f"{callback_prefix}:0"),
            ]
        ]
    )


def migraine_symptoms(lang: str, selected: list[str]) -> InlineKeyboardMarkup:
    """Toggle buttons, one per symptom (✅ when selected), plus Done."""
    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if key in selected else "") + t(lang, f"migraine.sym.{key}"),
                callback_data=f"mg_sym:{key}",
            )
        ]
        for key in SYMPTOMS
    ]
    rows.append(
        [InlineKeyboardButton(text=t(lang, "migraine.btn_done"), callback_data="mg_sym:done")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def migraine_single(lang: str, label_key: str, callback_data: str) -> InlineKeyboardMarkup:
    """One button — 'Nothing' / 'Skip' under a free-text question."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, label_key), callback_data=callback_data)]]
    )


def migraine_after_start(lang: str, entry_id: int) -> InlineKeyboardMarkup:
    """'Still going' / 'It's over' right after an attack is saved."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "migraine.btn_still"), callback_data=f"mg_still:{entry_id}"),
                InlineKeyboardButton(text=t(lang, "migraine.btn_over"), callback_data=f"mg_end:{entry_id}"),
            ]
        ]
    )


def migraine_over_button(lang: str, entry_id: int, *, offer_new: bool = False) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=t(lang, "migraine.btn_over"), callback_data=f"mg_end:{entry_id}")]
    if offer_new:
        row.append(InlineKeyboardButton(text=t(lang, "migraine.btn_new"), callback_data="mg_new"))
    return InlineKeyboardMarkup(inline_keyboard=[row])
