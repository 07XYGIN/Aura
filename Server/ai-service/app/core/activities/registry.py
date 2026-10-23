"""Ordered registry for optional conversation activities."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.models import ActivityResult, TurnRequest

from .base import ActivityHandler


class ActivityRegistry:
    def __init__(self, handlers: Iterable[ActivityHandler] = ()) -> None:
        self._handlers = tuple(handlers)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(handler.name for handler in self._handlers)

    async def dispatch(
        self,
        session: AsyncSession,
        request: TurnRequest,
    ) -> ActivityResult | None:
        for handler in self._handlers:
            result = await handler.try_handle(session, request)
            if result is not None:
                return result
        return None


def build_default_activity_registry() -> ActivityRegistry:
    """Build the registry shipped by Aura.

    The product currently has no built-in activities. Integrations can still
    construct an ``ActivityRegistry`` with their own handlers.
    """

    return ActivityRegistry()
