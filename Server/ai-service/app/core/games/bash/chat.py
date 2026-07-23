"""巴什博弈与主聊天入口之间的高置信度分流。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.game import BashGameMoveRequest, BashGameStartRequest

from .narrator import bash_rules_message, build_bash_game_messages, build_status_message
from .parser import BashChatIntent, parse_bash_chat_intent
from .service import (
    BashGameServiceError,
    get_active_bash_game,
    build_bash_game_snapshot,
    perform_user_move,
    resign_bash_game,
    start_bash_game,
)


@dataclass(frozen=True)
class BashChatResponse:
    """聊天分流命中后交给 SSE 层的完整结果。

    Attributes:
        action: 本轮游戏动作名称。
        snapshot: 已提交的棋局快照；纯规则说明时为空。
        messages: 要作为 Aura 消息写入历史并返回客户端的文本列表。
    """

    action: str
    snapshot: dict[str, Any] | None
    messages: list[str]


async def try_handle_bash_chat_message(
    session: AsyncSession,
    *,
    message: str,
    user_id: str,
    client_message_id: str | None,
) -> BashChatResponse | None:
    """识别并执行一条明确的巴什博弈聊天命令。

    Args:
        session: 当前请求使用的异步数据库会话。
        message: 用户原始聊天文本。
        user_id: 当前聊天用户 ID。
        client_message_id: 客户端回合 ID，同时用作开始/落子的幂等键；缺失时
            为本次请求生成随机键。

    Returns:
        命中游戏命令时返回已持久化结果；普通聊天返回 ``None``，调用方应继续
        执行原有 Aura Agent。

    Raises:
        BashGameServiceError: 明确游戏命令违反规则或发生版本/状态冲突。调用方
            应把消息作为中文游戏回复，不要回退到 LLM 猜测。

    Side Effects:
        ``start``、``move`` 和 ``resign`` 会通过事务服务提交数据库；``status``
        和 ``rules`` 只读。
    """

    candidate = parse_bash_chat_intent(message, has_active_game=True)
    if candidate is None:
        return None

    explicit_intent = parse_bash_chat_intent(message, has_active_game=False)
    try:
        active_game = await get_active_bash_game(session, user_id)
    except BashGameServiceError:
        if explicit_intent is not None:
            raise
        return None
    intent = explicit_intent or parse_bash_chat_intent(message, has_active_game=active_game is not None)
    if intent is None:
        return None
    if intent.action == "rules":
        return BashChatResponse("rules", None, [bash_rules_message()])
    if intent.action == "start":
        if active_game is not None:
            snapshot = await build_bash_game_snapshot(session, active_game, action="status")
            return BashChatResponse("status", snapshot, ["这局还没结束呢。" + build_status_message(snapshot["game"])])
        snapshot = await start_bash_game(
            session,
            user_id,
            BashGameStartRequest(
                startRequestId=client_message_id or f"chat-start-{uuid4()}",
            ),
        )
        return BashChatResponse("started", snapshot, build_bash_game_messages(snapshot))
    if active_game is None:
        return None
    if intent.action == "status":
        snapshot = await build_bash_game_snapshot(session, active_game, action="status")
        return BashChatResponse("status", snapshot, build_bash_game_messages(snapshot))
    if intent.action == "resign":
        snapshot = await resign_bash_game(
            session,
            user_id,
            str(active_game.id),
            active_game.version,
        )
        return BashChatResponse("resigned", snapshot, build_bash_game_messages(snapshot))
    return await handle_move_intent(
        session,
        intent,
        user_id=user_id,
        active_game=active_game,
        client_message_id=client_message_id,
    )


async def handle_move_intent(
    session: AsyncSession,
    intent: BashChatIntent,
    *,
    user_id: str,
    active_game: Any,
    client_message_id: str | None,
) -> BashChatResponse:
    """把已解析的 move 意图转换成幂等事务请求并生成聊天结果。

    Raises:
        BashGameServiceError: 意图缺少取子数，或事务服务拒绝本次行动。
    """

    if intent.action != "move" or intent.take_count is None:
        raise BashGameServiceError("没有识别出要拿走几颗石子")
    snapshot = await perform_user_move(
        session,
        user_id,
        str(active_game.id),
        BashGameMoveRequest(
            takeCount=intent.take_count,
            expectedVersion=active_game.version,
            clientMoveId=client_message_id or f"chat-move-{uuid4()}",
        ),
    )
    return BashChatResponse("moved", snapshot, build_bash_game_messages(snapshot))
