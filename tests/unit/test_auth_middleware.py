from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.middlewares.auth import AllowlistMiddleware


async def test_allowlisted_user_passes() -> None:
    mw = AllowlistMiddleware(frozenset({100, 200}))
    handler = AsyncMock(return_value="ok")
    event = MagicMock()
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
