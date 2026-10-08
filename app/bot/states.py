from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class LogFlow(StatesGroup):
    pick_metric = State()
    enter_value = State()


class QuickFlow(StatesGroup):
    pick_value = State()


class ThoughtFlow(StatesGroup):
    situation = State()
    automatic_thought = State()
    distortion = State()
    reframe = State()


class JournalFlow(StatesGroup):
    enter_text = State()


class ActivateFlow(StatesGroup):
    plan_text = State()
    pick_when = State()
    pick_predicted_effect = State()


class DoneFlow(StatesGroup):
    pick_actual_effect = State()


class SkipFlow(StatesGroup):
    enter_reason = State()


class MigraineFlow(StatesGroup):
    # Only the free-text steps need state; every button on the attack card
    # carries its entry id (mg:<action>:<id>) and works statelessly.
    # Data: entry_id, prompt_id, plus field/closing/meds per step.
    typed_time = State()
    medication = State()
    trigger_text = State()


class PlainTextFlow(StatesGroup):
    # Free text sent outside any command, waiting for "note / thought / ask".
    # The text sits in FSM data (encrypted at rest by PgFsmStorage), never in
    # callback data.
    pending = State()


class AskFlow(StatesGroup):
    question = State()


class DayFlow(StatesGroup):
    # Data: step (index into DAY_METRICS), ids, readings.
    active = State()


class RecentFlow(StatesGroup):
    edit_text = State()  # data: entry_id, prompt_id
