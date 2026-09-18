"""Application orchestration for one Aura conversation turn."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Iterable
from typing import Any

from app.core.activities.registry import ActivityRegistry, build_default_activity_registry
from app.core.agent.agent_graph import append_external_history_turn
from app.core.agent.models import (
    ActivityResult,
    InteractionMode,
    InteractionState,
    TurnPlan,
    TurnRequest,
)
from app.core.agent.protocol import (
    SSEProtocolV1,
    assistant_message_event,
    bash_game_state_event,
    content_event,
    focus_state_event,
    pet_state_event,
    turn_lifecycle_event,
)
from app.core.config import AURA_OPTIONAL_ACTIVITIES_ENABLED
from app.core.continuity.capsules import trigger_keyword_messages
from app.db.session import AsyncSessionLocal


AgentRunner = Callable[..., Iterable[dict[str, Any]]]


class TurnOrchestrator:
    """Coordinates turn routing while keeping HTTP and domain services separate."""

    def __init__(
        self,
        activity_registry: ActivityRegistry | None = None,
        *,
        activities_enabled: bool | None = None,
    ) -> None:
        self.activity_registry = activity_registry or build_default_activity_registry()
        self.activities_enabled = (
            AURA_OPTIONAL_ACTIVITIES_ENABLED
            if activities_enabled is None
            else activities_enabled
        )

    async def prepare(self, request: TurnRequest) -> TurnPlan:
        if request.retry_message_id:
            return TurnPlan(
                request=request,
                interaction=InteractionState(
                    mode=InteractionMode.RETRY,
                    branch_id=request.branch_id,
                    retry_message_id=request.retry_message_id,
                ),
            )
        if self.activities_enabled and request.branch_id is None:
            async with AsyncSessionLocal() as session:
                activity = await self.activity_registry.dispatch(session, request)
            if activity is not None:
                return TurnPlan(
                    request=request,
                    interaction=InteractionState(
                        mode=InteractionMode.ACTIVITY,
                        activity=activity.activity,
                    ),
                    activity_result=activity,
                )
        return TurnPlan(
            request=request,
            interaction=InteractionState(
                mode=InteractionMode.NORMAL,
                branch_id=request.branch_id,
            ),
        )

    async def stream_activity(self, plan: TurnPlan) -> AsyncIterator[str]:
        result = plan.activity_result
        if result is None:
            raise ValueError("activity turn is missing activity_result")
        protocol = SSEProtocolV1(plan.request.client_message_id)
        yield protocol.encode(turn_lifecycle_event("started"))
        state_event = self._activity_state_event(result)
        if state_event is not None:
            yield protocol.encode(state_event)

        reply_batch = None
        idempotent_replay = bool(
            result.snapshot and result.snapshot.get("idempotentReplay")
        )
        if not idempotent_replay:
            try:
                reply_batch = await asyncio.to_thread(
                    append_external_history_turn,
                    plan.request.user_id,
                    plan.request.message,
                    result.messages,
                    source=result.activity,
                    turn_id=plan.request.client_message_id,
                    client_message_id=plan.request.client_message_id,
                    source_metadata=result.source_metadata,
                )
            except Exception:
                logging.exception(
                    "活动消息写入统一聊天历史失败 activity=%s",
                    result.activity,
                )
        if reply_batch:
            await self._trigger_keyword(plan.request, source=result.activity)
            for item in reply_batch.get("messages", []):
                yield protocol.encode(
                    assistant_message_event(
                        content=item["content"],
                        message_id=item["message_id"],
                        batch_id=item["batch_id"],
                        batch_index=item["batch_index"],
                        batch_total=item["batch_total"],
                        delay_ms=item["delay_ms"],
                        sent_at=item["sent_at"],
                    )
                )
        else:
            for content in result.messages:
                yield protocol.encode(content_event(content))
        yield protocol.encode(turn_lifecycle_event("completed"))
        yield "data: [DONE]\n\n"

    @staticmethod
    def _activity_state_event(result: ActivityResult) -> dict[str, Any] | None:
        if result.snapshot is None:
            return None
        builders = {
            "focus": focus_state_event,
            "bash_game": bash_game_state_event,
            "pet": pet_state_event,
        }
        builder = builders.get(result.activity)
        return builder(result.snapshot) if builder else None

    @staticmethod
    async def _trigger_keyword(request: TurnRequest, *, source: str) -> None:
        if not request.client_message_id:
            return
        try:
            async with AsyncSessionLocal() as session:
                await trigger_keyword_messages(
                    session,
                    request.user_id,
                    request.message,
                    event_id=f"chat:{request.client_message_id}",
                )
        except Exception:
            logging.exception(
                "活动回合关键词条件评估失败 activity=%s user_id=%s",
                source,
                request.user_id,
            )
