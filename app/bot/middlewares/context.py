from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.di import Container


class ContextMiddleware(BaseMiddleware):
    """Injects the DI container, settings and cipher into handler kwargs."""

    def __init__(self, container: Container) -> None:
        self._container = container

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["container"] = self._container
        data["settings"] = self._container.settings
        data["cipher"] = self._container.cipher
        return await handler(event, data)
