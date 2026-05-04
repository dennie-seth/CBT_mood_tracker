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
