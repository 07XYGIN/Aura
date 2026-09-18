"""Adapters from existing activity services to the common plugin contract."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.models import ActivityResult, TurnRequest
from app.core.focus.chat import FocusChatResponse, try_handle_focus_chat_message
from app.core.focus.service import FocusServiceError
from app.core.games.bash.chat import BashChatResponse, try_handle_bash_chat_message
from app.core.games.bash.service import BashGameServiceError
from app.core.pet.chat import PetChatResponse, try_handle_pet_chat_message
from app.core.pet.service import PetServiceError


ResponseT = TypeVar("ResponseT", FocusChatResponse, BashChatResponse, PetChatResponse)


def _metadata(activity: str, response: ResponseT) -> dict[str, object]:
    metadata: dict[str, object] = {f"{activity}_action": response.action}
    snapshot = response.snapshot or {}
    entity_key = {"bash_game": "game", "pet": "pet", "focus": "focus"}[activity]
    entity = snapshot.get(entity_key) or {}
    if isinstance(entity, dict):
        metadata[f"{activity}_id"] = entity.get("id")
        metadata[f"{activity}_version"] = entity.get("version")
    return metadata


@dataclass(frozen=True)
class ExistingActivityAdapter:
    name: str
    handler: Callable[..., Awaitable[ResponseT | None]]
    service_error: type[Exception]

    async def try_handle(
        self,
        session: AsyncSession,
        request: TurnRequest,
    ) -> ActivityResult | None:
        try:
            response = await self.handler(
                session,
                message=request.message,
                user_id=request.user_id,
                client_message_id=request.client_message_id,
            )
        except self.service_error as exc:
            return ActivityResult(
                activity=self.name,
                action="rejected",
                messages=[str(exc)],
            )
        except Exception:
            logging.exception("活动分流失败 activity=%s，继续尝试普通对话", self.name)
            return None
        if response is None:
            return None
        return ActivityResult(
            activity=self.name,
            action=response.action,
            snapshot=response.snapshot,
            messages=response.messages,
            source_metadata=_metadata(self.name, response),
        )


def default_activity_adapters() -> list[ExistingActivityAdapter]:
    return [
        ExistingActivityAdapter("focus", try_handle_focus_chat_message, FocusServiceError),
        ExistingActivityAdapter("bash_game", try_handle_bash_chat_message, BashGameServiceError),
        ExistingActivityAdapter("pet", try_handle_pet_chat_message, PetServiceError),
    ]

