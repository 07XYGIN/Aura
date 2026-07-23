"""共同宠物与主聊天入口之间的确定性分流。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.pet import PetActionRequest, PetAdoptRequest, PetRenameRequest

from .narrator import pet_snapshot_messages
from .parser import PetChatIntent, is_pet_chat_candidate, parse_pet_chat_intent
from .service import (
    PetServiceError,
    adopt_pet,
    get_pet_for_user,
    get_pet_snapshot,
    perform_pet_action,
    rename_pet,
)


@dataclass(frozen=True)
class PetChatResponse:
    """宠物聊天命令执行后交给 SSE 层的状态和文案。"""

    action: str
    snapshot: dict[str, Any] | None
    messages: list[str]


async def try_handle_pet_chat_message(
    session: AsyncSession,
    *,
    message: str,
    user_id: str,
    client_message_id: str | None,
) -> PetChatResponse | None:
    """识别并执行一条明确的宠物聊天命令。

    普通文本在粗筛阶段直接返回 ``None``，不会额外查询数据库。命中动作后所有
    状态变化都由宠物事务服务完成，主模型不能自行决定数值或制造事件。
    """

    if not is_pet_chat_candidate(message):
        return None
    explicit_intent = parse_pet_chat_intent(message, has_pet=False)
    try:
        pet = await get_pet_for_user(session, user_id)
    except PetServiceError:
        if explicit_intent is not None:
            raise
        return None
    intent = explicit_intent or parse_pet_chat_intent(
        message,
        has_pet=pet is not None,
        pet_name=pet.name if pet is not None else None,
    )
    if intent is None:
        return None
    if intent.action == "adopt_prompt":
        return PetChatResponse(
            "adopt_prompt",
            None,
            ["可以呀。想养小猫、小狗还是小兔子？再给它取个名字，比如“养一只猫，叫团子”。"],
        )
    if intent.action == "adopt":
        if not intent.name or not intent.species:
            raise PetServiceError("领养时需要确定宠物种类和名字")
        action_id = require_pet_chat_action_id(client_message_id)
        snapshot = await adopt_pet(
            session,
            user_id,
            PetAdoptRequest(
                name=intent.name,
                species=intent.species,
                personality="gentle",
                adoptionRequestId=action_id,
            ),
        )
        return PetChatResponse("adopted", snapshot, pet_snapshot_messages(snapshot))
    if pet is None:
        return PetChatResponse("no_pet", None, ["我们还没有领养宠物。先一起选一只，再给它取个名字吧。"])
    if intent.action == "status":
        snapshot = await get_pet_snapshot(session, user_id)
        if snapshot is None:
            return PetChatResponse("no_pet", None, ["我们还没有领养共同宠物。"])
        return PetChatResponse("status", snapshot, pet_snapshot_messages(snapshot))
    if intent.action == "rename":
        if not intent.name:
            raise PetServiceError("没有识别出新的宠物名字")
        action_id = require_pet_chat_action_id(client_message_id)
        snapshot = await rename_pet(
            session,
            user_id,
            PetRenameRequest(
                name=intent.name,
                clientActionId=action_id,
                expectedVersion=pet.version,
            ),
        )
        return PetChatResponse("renamed", snapshot, pet_snapshot_messages(snapshot))
    return await handle_pet_action_intent(
        session,
        intent,
        user_id=user_id,
        pet=pet,
        client_message_id=client_message_id,
    )


async def handle_pet_action_intent(
    session: AsyncSession,
    intent: PetChatIntent,
    *,
    user_id: str,
    pet: Any,
    client_message_id: str | None,
) -> PetChatResponse:
    """把已解析照顾动作转换为带版本和幂等键的事务请求。"""

    if intent.action not in {"feed", "play", "groom", "bathe", "pet", "sleep"}:
        raise PetServiceError("没有识别出要怎样照顾宠物")
    action_id = require_pet_chat_action_id(client_message_id)
    snapshot = await perform_pet_action(
        session,
        user_id,
        PetActionRequest(
            action=intent.action,
            clientActionId=action_id,
            expectedVersion=pet.version,
        ),
    )
    return PetChatResponse(intent.action, snapshot, pet_snapshot_messages(snapshot))


def require_pet_chat_action_id(client_message_id: str | None) -> str:
    """返回稳定客户端回合 ID，写操作缺失时拒绝执行。

    随机生成服务端 ID 无法跨 HTTP 超时重试复现，因此领养、照顾和改名必须由
    客户端提供 ``clientMessageId``。只读状态和领养咨询不受此限制。

    Raises:
        PetServiceError: ID 缺失或清理后为空。
    """

    action_id = str(client_message_id or "").strip()
    if not action_id:
        raise PetServiceError("宠物写操作需要 clientMessageId，避免网络重试时重复执行")
    return action_id
