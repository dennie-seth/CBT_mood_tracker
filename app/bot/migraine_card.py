"""Attack card: the one message that shows a migraine attack and edits it.

Pure presentation — no IO. Buttons carry `mg:<action>:<entry_id>[:<arg>]`,
so they keep working without FSM state; the handler re-loads the attack
(with an ownership check) on every tap.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import pytz
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.i18n import t
from app.services.entry_service import EntryDTO
from app.services.migraine_service import MigraineService
from app.services.migraine_stats import MEDICATION_DAYS_FLAG, MigraineStats

_STALE_AFTER = MigraineService.STALE_AFTER


def cb(action: str, entry_id: int, *args: object) -> str:
    return ":".join(["mg", action, str(entry_id), *map(str, args)])


def _btn(lang: str, key: str, data: str, **fmt: object) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=t(lang, key, **fmt), callback_data=data)


def fmt_duration(minutes: int, lang: str) -> str:
    d, rem = divmod(max(minutes, 0), 24 * 60)
    h, m = divmod(rem, 60)
    if d:
        return t(lang, "migraine.duration_days", d=d, h=h)
    if h:
        return t(lang, "migraine.duration", h=h, m=m)
    return t(lang, "migraine.duration_min", m=m)


def fmt_when(iso: str, lang: str, tz_name: str, now: datetime) -> str:
    """'14:30' today, 'yesterday 14:30', else '2026-10-06 14:30' (user tz)."""
    tz = pytz.timezone(tz_name)
    local = datetime.fromisoformat(iso).astimezone(tz)
    today = now.astimezone(tz).date()
    hhmm = local.strftime("%H:%M")
    if local.date() == today:
        return hhmm
    if (today - local.date()).days == 1:
        return t(lang, "migraine.when.yesterday", time=hhmm)
    return local.strftime("%Y-%m-%d %H:%M")


def _list(lang: str, prefix: str, keys: list[str]) -> list[str]:
    return [t(lang, f"migraine.{prefix}.{k}") for k in keys]


def _peak(extra: dict[str, Any]) -> int:
    start = int(extra.get("start_intensity") or 0)
    return max(start, int(extra.get("peak_intensity") or start))


def render_card(
    attack: EntryDTO, lang: str, tz_name: str, now: datetime, *, footer: str | None = None
) -> tuple[str, InlineKeyboardMarkup]:
    x = attack.extra or {}
    none = t(lang, "migraine.card.none")
    is_open = x.get("status") == "ongoing"
    started_iso = x.get("started_at") or attack.recorded_at.isoformat()
    started = datetime.fromisoformat(started_iso)
    stale = is_open and now - started > _STALE_AFTER

    lines = [t(lang, "migraine.card.title_open" if is_open else "migraine.card.title_ended")]
    when = fmt_when(started_iso, lang, tz_name, now)
    if is_open:
        ago = fmt_duration(int((now - started).total_seconds() // 60), lang)
        lines.append(t(lang, "migraine.card.started_ago", when=when, ago=ago))
    else:
        lines.append(t(lang, "migraine.card.started", when=when))
        if x.get("ended_at"):
            lines.append(t(
                lang, "migraine.card.ended",
                when=fmt_when(x["ended_at"], lang, tz_name, now),
                duration=fmt_duration(int(x.get("duration_minutes") or 0), lang),
            ))
        else:
            lines.append(t(lang, "migraine.card.ended_unknown"))

    lines.append(t(
        lang, "migraine.card.intensity",
        start=x.get("start_intensity", "?"), peak=_peak(x),
    ))
    aura = x.get("aura")
    lines.append(t(lang, "migraine.card.aura", value=(
        none if aura is None else t(lang, "migraine.card.yes" if aura else "migraine.card.no")
    )))
    lines.append(t(lang, "migraine.card.symptoms",
                   value=", ".join(_list(lang, "sym", x.get("symptoms") or [])) or none))
    triggers = _list(lang, "trg", x.get("triggers") or [])
    if x.get("trigger_text"):
        triggers.append(f"“{x['trigger_text']}”")
    lines.append(t(lang, "migraine.card.triggers", value=", ".join(triggers) or none))
    med = x.get("medication_text")
    med_value = med or none
    if med and x.get("relief") is not None:
        med_value += t(lang, "migraine.card.relief", relief=x["relief"])
    lines.append(t(lang, "migraine.card.medication", value=med_value))

    if stale:
        lines.append("")
        lines.append(t(lang, "migraine.card.stale",
                       duration=fmt_duration(int((now - started).total_seconds() // 60), lang)))
    if footer:
        lines.append("")
        lines.append(footer)

    i = attack.id
    rows: list[list[InlineKeyboardButton]] = []
    if is_open:
        rows.append([_btn(lang, "migraine.btn.over", cb("over", i))])
        if stale:
            rows.append([_btn(lang, "migraine.btn.forgot_end", cb("forgot", i))])
        rows.append([
            _btn(lang, "migraine.btn.start_time", cb("start", i)),
            _btn(lang, "migraine.btn.worse", cb("worse", i)),
        ])
    else:
        rows.append([
            _btn(lang, "migraine.btn.start_time", cb("start", i)),
            _btn(lang, "migraine.btn.end_time", cb("endtime", i)),
        ])
        rows.append([_btn(lang, "migraine.btn.peak", cb("worse", i))])
    rows.append([
        _btn(lang, "migraine.btn.aura", cb("aura", i)),
        _btn(lang, "migraine.btn.symptoms", cb("sym", i)),
    ])
    med_row = [_btn(lang, "migraine.btn.medication", cb("med", i))]
    if med:
        med_row.append(_btn(lang, "migraine.btn.relief", cb("relief", i)))
    rows.append(med_row)
    rows.append([
        _btn(lang, "migraine.btn.triggers", cb("trg", i)),
        _btn(lang, "migraine.btn.delete", cb("del", i)),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def summary_line(attack: EntryDTO, lang: str, tz_name: str, now: datetime) -> str:
    """One compact line for /today and /week."""
    x = attack.extra or {}
    peak = _peak(x) if x else int(attack.value_numeric or 0)
    if not x.get("status"):  # plain numeric entry (e.g. /backfill)
        return str(peak)
    start = fmt_when(x["started_at"], lang, tz_name, now)
    if x["status"] == "ongoing":
        line = t(lang, "migraine.summary_open", start=start, peak=peak)
    elif x.get("ended_at"):
        tz = pytz.timezone(tz_name)
        end_local = datetime.fromisoformat(x["ended_at"]).astimezone(tz)
        start_local = datetime.fromisoformat(x["started_at"]).astimezone(tz)
        end = (
            end_local.strftime("%H:%M") if end_local.date() == start_local.date()
            else fmt_when(x["ended_at"], lang, tz_name, now)
        )
        line = t(
            lang, "migraine.summary", span=f"{start}–{end}",
            duration=fmt_duration(int(x.get("duration_minutes") or 0), lang), peak=peak,
        )
    else:
        line = t(lang, "migraine.summary_unknown_end", start=start, peak=peak)
    if x.get("medication_text"):
        line += t(lang, "migraine.summary_med", med=x["medication_text"])
        if x.get("relief") is not None:
            line += t(lang, "migraine.summary_relief", relief=x["relief"])
    return line


# --- sub-screens ------------------------------------------------------------
# Every sub-screen has a way back to the card, so nothing is a dead end.

_HOURS_AGO: tuple[int, ...] = (1, 2, 4, 8)


def _back_row(lang: str, entry_id: int) -> list[InlineKeyboardButton]:
    return [_btn(lang, "migraine.btn.back", cb("card", entry_id))]


def time_picker(
    lang: str, action: str, entry_id: int, *, include_now: bool,
    extra_rows: Sequence[list[InlineKeyboardButton]] = (),
) -> InlineKeyboardMarkup:
    """Now? / 1h / 2h / 4h / 8h ago. Arg = minutes ago."""
    rows: list[list[InlineKeyboardButton]] = []
    if include_now:
        rows.append([_btn(lang, "migraine.btn.now", cb(action, entry_id, 0))])
    rows.append([
        _btn(lang, "migraine.btn.ago", cb(action, entry_id, h * 60), h=h) for h in _HOURS_AGO
    ])
    rows.extend(extra_rows)
    rows.append(_back_row(lang, entry_id))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def scale(action: str, entry_id: int, lang: str | None = None) -> InlineKeyboardMarkup:
    """1..10 in two rows; with `lang`, adds a Back row."""
    rows = [
        [InlineKeyboardButton(text=str(n), callback_data=cb(action, entry_id, n)) for n in rng]
        for rng in (range(1, 6), range(6, 11))
    ]
    if lang is not None:
        rows.append(_back_row(lang, entry_id))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def yes_no(lang: str, entry_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            _btn(lang, "migraine.btn.yes", cb("au", entry_id, 1)),
            _btn(lang, "migraine.btn.no", cb("au", entry_id, 0)),
        ],
        _back_row(lang, entry_id),
    ])


def toggles(
    lang: str, entry_id: int, *, action: str, label_prefix: str,
    keys: tuple[str, ...], selected: list[str],
    extra_rows: Sequence[list[InlineKeyboardButton]] = (),
) -> InlineKeyboardMarkup:
    """Two-per-row toggles (✅ when selected) + Done back to the card."""
    buttons = [
        InlineKeyboardButton(
            text=("✅ " if k in selected else "") + t(lang, f"migraine.{label_prefix}.{k}"),
            callback_data=cb(action, entry_id, k),
        )
        for k in keys
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.extend(extra_rows)
    rows.append([_btn(lang, "migraine.btn.done", cb("card", entry_id))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def med_picker(
    lang: str, entry_id: int, meds: list[str], *, closing: bool, has_med: bool
) -> InlineKeyboardMarkup:
    """Recent medications as buttons (arg = index into the list kept in FSM
    data — the text itself never goes into callback data)."""
    rows = [
        [InlineKeyboardButton(
            text=m if len(m) <= 40 else m[:39] + "…",
            callback_data=cb("mp", entry_id, i),
        )]
        for i, m in enumerate(meds)
    ]
    if closing:
        rows.append([_btn(lang, "migraine.btn.no_med", cb("nomed", entry_id))])
    else:
        if has_med:
            rows.append([_btn(lang, "migraine.btn.clear", cb("mx", entry_id))])
        rows.append(_back_row(lang, entry_id))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete(lang: str, entry_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(lang, "migraine.btn.delete_yes", cb("dely", entry_id))],
        _back_row(lang, entry_id),
    ])


# --- /migraines summary -------------------------------------------------------

def _counted(lang: str, prefix: str, counts: dict[str, int], limit: int = 4) -> str:
    return ", ".join(
        f"{t(lang, f'migraine.{prefix}.{k}')} ×{n}" for k, n in list(counts.items())[:limit]
    )


def render_summary(stats: MigraineStats, *, med_days_last_30: int, lang: str) -> str:
    start, end = stats.start.isoformat(), stats.end.isoformat()
    if stats.attacks == 0:
        return t(lang, "migraines.empty", start=start, end=end)
    lines = [t(lang, "migraines.header", start=start, end=end), ""]
    attacks = t(lang, "migraines.attacks", n=stats.attacks, days=stats.headache_days)
    if stats.open_attacks:
        attacks += t(lang, "migraines.open", n=stats.open_attacks)
    lines.append(attacks)
    if stats.avg_duration_minutes is not None and stats.longest_minutes is not None:
        lines.append(t(
            lang, "migraines.duration",
            avg=fmt_duration(stats.avg_duration_minutes, lang),
            longest=fmt_duration(stats.longest_minutes, lang),
        ))
    if stats.avg_peak is not None:
        lines.append(t(lang, "migraines.peak", avg=stats.avg_peak, max=stats.max_peak))
    if stats.aura:
        lines.append(t(lang, "migraines.aura", n=stats.aura, total=stats.attacks))
    if stats.symptoms:
        lines.append(t(lang, "migraines.symptoms", items=_counted(lang, "sym", stats.symptoms)))
    if stats.triggers:
        lines.append(t(lang, "migraines.triggers", items=_counted(lang, "trg", stats.triggers)))
    if stats.medications:
        lines.append("")
        lines.append(t(lang, "migraines.meds_header"))
        for m in stats.medications:
            line = t(lang, "migraines.med_line", name=m.name, n=m.attacks)
            if m.avg_relief is not None:
                line += t(lang, "migraines.med_relief", relief=m.avg_relief)
            lines.append(line)
    if med_days_last_30:
        lines.append("")
        lines.append(t(lang, "migraines.med_days", n=med_days_last_30))
        if med_days_last_30 >= MEDICATION_DAYS_FLAG:
            lines.append(t(lang, "migraines.med_flag"))
    return "\n".join(lines)
