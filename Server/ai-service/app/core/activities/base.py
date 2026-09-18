"""Contracts for deterministic chat activities."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.models import ActivityResult, TurnRequest


class ActivityHandler(Protocol):
    """A handler may claim a turn and return a committed activity result."""

    name: str

    async def try_handle(
        self,
        session: AsyncSession,
        request: TurnRequest,
    ) -> ActivityResult | None: ...

