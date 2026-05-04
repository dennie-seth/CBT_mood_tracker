from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Chat, Message

from app.bot.middlewares.auth import AllowlistMiddleware


def _msg(chat_type: str = "private", chat_id: int = 100) -> MagicMock:
    """A Message-shaped mock with .chat.type and .chat.id."""
    m = MagicMock(spec=Message)
    m.chat = MagicMock(spec=Chat)
    m.chat.type = chat_type
    m.chat.id = chat_id
    m.answer = AsyncMock()
    return m


async def test_allowlisted_user_in_private_chat_passes() -> None:
    mw = AllowlistMiddleware(frozenset({100, 200}))
    handler = AsyncMock(return_value="ok")
    event = _msg(chat_type="private", chat_id=100)
    tg_user = MagicMock(id=100)
    data = {"event_from_user": tg_user}

    result = await mw(handler, event, data)

    assert result == "ok"
    handler.assert_awaited_once_with(event, data)


async def test_non_allowlisted_user_rejected() -> None:
    mw = AllowlistMiddleware(frozenset({100}))
    handler = AsyncMock(return_value="should_not_run")
    event = MagicMock()
    tg_user = MagicMock(id=999)
    data = {"event_from_user": tg_user}

    result = await mw(handler, event, data)

    assert result is None
    handler.assert_not_awaited()


async def test_no_user_dropped_silently() -> None:
    mw = AllowlistMiddleware(frozenset({100}))
    handler = AsyncMock()
    event = MagicMock()
    data: dict = {}

    result = await mw(handler, event, data)

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.parametrize("chat_type", ["group", "supergroup", "channel"])
async def test_non_private_chat_rejected_even_for_allowlisted_user(chat_type: str) -> None:
    """Adding the bot to a group/channel must NOT exfiltrate decrypted notes,
    /today output, /export PDFs etc. into the group, where non-allowlisted
    members could read them."""
    mw = AllowlistMiddleware(frozenset({100}))
    handler = AsyncMock(return_value="leaked")
    event = _msg(chat_type=chat_type, chat_id=-9999)
    tg_user = MagicMock(id=100)  # allowlisted
    data = {"event_from_user": tg_user}

    result = await mw(handler, event, data)

    assert result is None
    handler.assert_not_awaited()


async def test_callback_query_in_private_chat_passes() -> None:
    """Callback queries from inline keyboards in private chats must still work."""
    mw = AllowlistMiddleware(frozenset({100}))
    handler = AsyncMock(return_value="ok")
    cb = MagicMock(spec=CallbackQuery)
    cb.message = _msg(chat_type="private", chat_id=100)
    cb.answer = AsyncMock()
    tg_user = MagicMock(id=100)
    data = {"event_from_user": tg_user}

    result = await mw(handler, cb, data)

    assert result == "ok"


async def test_non_allowlisted_callback_gets_alert_refusal() -> None:
    """CallbackQuery from a non-allowlisted user must be answered (no silent drop)."""
    mw = AllowlistMiddleware(frozenset({100}))
    handler = AsyncMock()
    cb = MagicMock(spec=CallbackQuery)
    cb.message = _msg(chat_type="private", chat_id=999)
    cb.answer = AsyncMock()
    tg_user = MagicMock(id=999)  # NOT in allowlist
    data = {"event_from_user": tg_user}

    result = await mw(handler, cb, data)

    assert result is None
    handler.assert_not_awaited()
    cb.answer.assert_awaited_once()  # alert/refusal sent


# --- Production-shaped: middleware runs at the Update observer level ---
#
# `dp.update.outer_middleware(...)` hands us the `Update` wrapper, not the
# inner `Message`/`CallbackQuery`. aiogram's internal user-context middleware
# populates `data["event_from_user"]` AND `data["event_chat"]` for us; we
# must read those, not try to dig into the event ourselves.

async def test_update_with_private_chat_passes_via_event_chat() -> None:
    mw = AllowlistMiddleware(frozenset({100}))
    handler = AsyncMock(return_value="ok")
    update = MagicMock()  # NOT a Message — actual production shape
    chat = MagicMock(type="private", id=100)
    data = {
        "event_from_user": MagicMock(id=100),
        "event_chat": chat,
    }

    result = await mw(handler, update, data)

    assert result == "ok"
    handler.assert_awaited_once_with(update, data)


@pytest.mark.parametrize("chat_type", ["group", "supergroup", "channel"])
async def test_update_with_non_private_chat_rejected(chat_type: str) -> None:
    """The middleware sees an `Update` wrapper at the outer level. It must
    still detect a non-private chat via `data['event_chat']`."""
    mw = AllowlistMiddleware(frozenset({100}))
    handler = AsyncMock(return_value="leaked")
    update = MagicMock()
    chat = MagicMock(type=chat_type, id=-9999)
    data = {
        "event_from_user": MagicMock(id=100),  # allowlisted
        "event_chat": chat,
    }

    result = await mw(handler, update, data)

    assert result is None
    handler.assert_not_awaited()


async def test_update_with_no_event_chat_refused_fail_closed() -> None:
    """If aiogram doesn't supply event_chat (e.g. inline_query), refuse."""
    mw = AllowlistMiddleware(frozenset({100}))
    handler = AsyncMock()
    update = MagicMock()
    data = {
        "event_from_user": MagicMock(id=100),
        # no event_chat
    }

    result = await mw(handler, update, data)

    assert result is None
    handler.assert_not_awaited()
