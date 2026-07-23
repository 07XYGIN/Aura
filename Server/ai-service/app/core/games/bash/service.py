"""巴什博弈的 PostgreSQL 事务服务。

会话行是当前棋局的权威状态，行动行是不可变审计事件。用户落子事务会锁定
会话行，并在同一事务内完成用户行动、Aura 回应行动和终局更新。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BashGameMove, BashGameSession
from app.schemas.game import BashGameMoveRequest, BashGameStartRequest

from .engine import BashRuleError, apply_take, choose_aura_take, validate_bash_rules


class BashGameServiceError(RuntimeError):
    """可安全转换为中文 HTTP 或聊天错误的游戏服务异常。

    Attributes:
        status_code: 建议返回给 HTTP 客户端的状态码。
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        """保存用户可读错误消息和对应 HTTP 状态码。"""

        super().__init__(message)
        self.status_code = status_code


def parse_user_id(user_id: str) -> UUID:
    """将外部用户 ID 转换为 UUID。

    Args:
        user_id: JWT ``sub`` 或聊天请求中的用户 ID。

    Returns:
        可用于 SQLAlchemy 查询的 UUID。

    Raises:
        BashGameServiceError: 用户 ID 不是合法 UUID。
    """

    try:
        return UUID(str(user_id))
    except (TypeError, ValueError) as exc:
        raise BashGameServiceError("用户 ID 无效", status_code=400) from exc


def parse_session_id(session_id: str) -> UUID:
    """将外部棋局 ID 转换为 UUID，格式无效时抛出 400 业务异常。"""

    try:
        return UUID(str(session_id))
    except (TypeError, ValueError) as exc:
        raise BashGameServiceError("棋局 ID 必须是有效的 UUID", status_code=400) from exc


def resolve_first_player(first_player: str, stable_key: str) -> str:
    """将 ``random`` 先手选项稳定解析为 ``user`` 或 ``aura``。

    使用请求 ID 的 SHA-256 首字节决定先手，因此同一开始请求在重试时不会
    改变结果；明确指定玩家时直接返回原值。
    """

    if first_player in {"user", "aura"}:
        return first_player
    if first_player != "random":
        raise BashGameServiceError("先手必须是 user、aura 或 random")
    digest = hashlib.sha256(stable_key.encode("utf-8")).digest()
    return "user" if digest[0] % 2 == 0 else "aura"


async def get_active_bash_game(
    session: AsyncSession,
    user_id: str,
    *,
    for_update: bool = False,
) -> BashGameSession | None:
    """查询用户当前唯一的进行中棋局。

    Args:
        session: 当前异步数据库会话。
        user_id: 棋局所属用户 ID。
        for_update: 为真时对命中的会话行加 ``FOR UPDATE`` 锁，调用方必须
            在同一事务内完成修改和提交。

    Returns:
        进行中的 ``BashGameSession``；没有活动棋局时返回 ``None``。
    """

    statement = select(BashGameSession).where(
        BashGameSession.user_id == parse_user_id(user_id),
        BashGameSession.status == "active",
    )
    if for_update:
        statement = statement.with_for_update()
    result = await session.execute(statement.limit(1))
    return result.scalar_one_or_none()


async def start_bash_game(
    session: AsyncSession,
    user_id: str,
    request: BashGameStartRequest,
) -> dict[str, Any]:
    """幂等创建一局巴什博弈，并在 Aura 先手时立即记录她的行动。

    Args:
        session: 用于查询、插入和提交的异步数据库会话。
        user_id: 从认证或聊天请求取得的棋局所有者 ID。
        request: 规则、难度、先手选择和开始请求 ID。

    Returns:
        可直接放入 API/SSE 的棋局快照，``action`` 为 ``started`` 或
        ``start_replayed``。

    Raises:
        BashGameServiceError: 规则无效、用户已有另一局进行中的游戏，或并发
            创建触发数据库唯一约束。

    Side Effects:
        新增一条会话记录；Aura 先手时同时新增行动记录；成功后提交事务。
    """

    try:
        validate_bash_rules(request.initial_stones, request.max_take)
    except BashRuleError as exc:
        raise BashGameServiceError(str(exc)) from exc

    parsed_user_id = parse_user_id(user_id)
    existing_result = await session.execute(
        select(BashGameSession).where(
            BashGameSession.user_id == parsed_user_id,
            BashGameSession.start_request_id == request.start_request_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return await build_bash_game_snapshot(
            session,
            existing,
            action="start_replayed",
            idempotent_replay=True,
        )

    active = await get_active_bash_game(session, user_id)
    if active is not None:
        raise BashGameServiceError("已经有一局巴什博弈正在进行", status_code=409)

    first_player = resolve_first_player(request.first_player, request.start_request_id)
    game = BashGameSession(
        user_id=parsed_user_id,
        initial_stones=request.initial_stones,
        remaining_stones=request.initial_stones,
        max_take=request.max_take,
        first_player=first_player,
        current_player=first_player,
        difficulty=request.difficulty,
        status="active",
        winner=None,
        version=0,
        start_request_id=request.start_request_id,
    )
    session.add(game)
    try:
        await session.flush()
        new_moves: list[BashGameMove] = []
        if first_player == "aura":
            aura_move = record_aura_move(game, turn_no=1)
            session.add(aura_move)
            new_moves.append(aura_move)
        await session.commit()
        await session.refresh(game)
    except IntegrityError as exc:
        await session.rollback()
        raise BashGameServiceError("棋局创建发生并发冲突，请读取当前棋局后重试", status_code=409) from exc

    return await build_bash_game_snapshot(
        session,
        game,
        action="started",
        new_moves=new_moves,
    )


async def get_bash_game(
    session: AsyncSession,
    user_id: str,
    session_id: str,
) -> BashGameSession:
    """按棋局 ID 和用户所有权查询会话。

    Raises:
        BashGameServiceError: ID 无效、棋局不存在或不属于当前用户；对外统一
            表现为 404，避免泄露其他用户的数据。
    """

    result = await session.execute(
        select(BashGameSession).where(
            BashGameSession.id == parse_session_id(session_id),
            BashGameSession.user_id == parse_user_id(user_id),
        )
    )
    game = result.scalar_one_or_none()
    if game is None:
        raise BashGameServiceError("没有找到这局巴什博弈", status_code=404)
    return game


async def get_current_bash_game_snapshot(
    session: AsyncSession,
    user_id: str,
) -> dict[str, Any] | None:
    """读取用户当前活动棋局的完整快照，没有活动棋局时返回 ``None``。"""

    game = await get_active_bash_game(session, user_id)
    if game is None:
        return None
    return await build_bash_game_snapshot(session, game, action="status")


async def get_bash_game_snapshot(
    session: AsyncSession,
    user_id: str,
    session_id: str,
) -> dict[str, Any]:
    """读取属于当前用户的指定棋局快照。"""

    game = await get_bash_game(session, user_id, session_id)
    return await build_bash_game_snapshot(session, game, action="status")


async def perform_user_move(
    session: AsyncSession,
    user_id: str,
    session_id: str,
    request: BashGameMoveRequest,
) -> dict[str, Any]:
    """原子执行用户行动和紧随其后的 Aura 行动。

    事务顺序是：锁定会话行、检查行动幂等键、比较版本、校验当前玩家、写入
    用户行动、按需写入 Aura 行动、更新终局与版本、提交。游戏状态和行动日志
    不会出现只成功一半的情况。

    Args:
        session: 当前异步数据库会话。
        user_id: 当前用户 ID，用于所有权校验。
        session_id: 要操作的棋局 UUID 字符串。
        request: 取子数、期望版本和客户端行动 ID。

    Returns:
        行动后的棋局快照；重复 ``client_move_id`` 会返回当前快照并设置
        ``idempotentReplay``，不会再次落子。

    Raises:
        BashGameServiceError: 棋局不存在、版本冲突、未轮到用户、棋局已结束，
            或取子数违反规则。

    Side Effects:
        在一个数据库事务中写入一到两条行动、更新会话并提交。
    """

    parsed_session_id = parse_session_id(session_id)
    result = await session.execute(
        select(BashGameSession)
        .where(
            BashGameSession.id == parsed_session_id,
            BashGameSession.user_id == parse_user_id(user_id),
        )
        .with_for_update()
    )
    game = result.scalar_one_or_none()
    if game is None:
        raise BashGameServiceError("没有找到这局巴什博弈", status_code=404)

    replay_result = await session.execute(
        select(BashGameMove).where(
            BashGameMove.session_id == game.id,
            BashGameMove.client_move_id == request.client_move_id,
        )
    )
    if replay_result.scalar_one_or_none() is not None:
        return await build_bash_game_snapshot(
            session,
            game,
            action="move_replayed",
            idempotent_replay=True,
        )

    ensure_active_version_and_turn(game, request.expected_version, expected_player="user")
    turn_no = await next_turn_number(session, game.id)
    try:
        user_move = record_move(
            game,
            turn_no=turn_no,
            player="user",
            take_count=request.take_count,
            client_move_id=request.client_move_id,
        )
    except BashRuleError as exc:
        raise BashGameServiceError(str(exc)) from exc

    session.add(user_move)
    new_moves = [user_move]
    if game.status == "active":
        aura_move = record_aura_move(game, turn_no=turn_no + 1)
        session.add(aura_move)
        new_moves.append(aura_move)

    game.version += 1
    try:
        await session.commit()
        await session.refresh(game)
    except IntegrityError as exc:
        await session.rollback()
        raise BashGameServiceError("这一步与另一条请求发生冲突，请刷新棋局后重试", status_code=409) from exc

    return await build_bash_game_snapshot(
        session,
        game,
        action="moved",
        new_moves=new_moves,
    )


async def resign_bash_game(
    session: AsyncSession,
    user_id: str,
    session_id: str,
    expected_version: int,
) -> dict[str, Any]:
    """锁定并结束一局活动游戏，将 Aura 记为胜者。

    已经处于 ``resigned`` 的棋局按幂等重试返回；正常结束的棋局不能再认输。
    版本不一致时返回 409，防止旧客户端覆盖已经发生的行动。
    """

    result = await session.execute(
        select(BashGameSession)
        .where(
            BashGameSession.id == parse_session_id(session_id),
            BashGameSession.user_id == parse_user_id(user_id),
        )
        .with_for_update()
    )
    game = result.scalar_one_or_none()
    if game is None:
        raise BashGameServiceError("没有找到这局巴什博弈", status_code=404)
    if game.status == "resigned":
        return await build_bash_game_snapshot(
            session,
            game,
            action="resign_replayed",
            idempotent_replay=True,
        )
    if game.status != "active":
        raise BashGameServiceError("这局游戏已经结束", status_code=409)
    if game.version != expected_version:
        raise BashGameServiceError(
            f"棋局版本已变化，当前版本是 {game.version}，请刷新后重试",
            status_code=409,
        )

    game.status = "resigned"
    game.winner = "aura"
    game.current_player = None
    game.finished_at = datetime.now(UTC)
    game.version += 1
    await session.commit()
    await session.refresh(game)
    return await build_bash_game_snapshot(session, game, action="resigned")


def ensure_active_version_and_turn(
    game: BashGameSession,
    expected_version: int,
    expected_player: str,
) -> None:
    """校验棋局仍活动、版本未过期且轮到指定玩家。

    Raises:
        BashGameServiceError: 任一前置条件不满足。状态与轮次冲突使用 409，便于
            客户端读取最新状态后决定是否重试。
    """

    if game.status != "active":
        raise BashGameServiceError("这局游戏已经结束", status_code=409)
    if game.version != expected_version:
        raise BashGameServiceError(
            f"棋局版本已变化，当前版本是 {game.version}，请刷新后重试",
            status_code=409,
        )
    if game.current_player != expected_player:
        raise BashGameServiceError("现在还没有轮到你", status_code=409)


async def next_turn_number(session: AsyncSession, session_id: UUID) -> int:
    """读取棋局当前最大行动序号并返回下一个序号。

    调用方必须已经锁定对应会话行，才能保证并发事务不会得到相同序号。
    """

    result = await session.execute(
        select(func.coalesce(func.max(BashGameMove.turn_no), 0)).where(
            BashGameMove.session_id == session_id
        )
    )
    return int(result.scalar_one()) + 1


def record_move(
    game: BashGameSession,
    *,
    turn_no: int,
    player: str,
    take_count: int,
    client_move_id: str | None,
    strategy: str | None = None,
) -> BashGameMove:
    """应用一次已确定玩家的行动并构造不可变 Move 实体。

    Args:
        game: 将被原地更新剩余数、轮次、胜者和结束时间的会话实体。
        turn_no: 本行动在棋局中的一基序号。
        player: ``user`` 或 ``aura``。
        take_count: 本回合取走的石子数。
        client_move_id: 用户行动的幂等键；Aura 行动必须为 ``None``。
        strategy: Aura 策略标签；用户行动通常为空。

    Returns:
        尚未写入数据库的 ``BashGameMove`` 实体。

    Raises:
        BashRuleError: 玩家、幂等键或取子数量不符合规则。

    Side Effects:
        原地修改 ``game`` 的权威局面；调用方负责把 Move 和 Session 放在同一
        数据库事务提交。
    """

    if player not in {"user", "aura"}:
        raise BashRuleError("行动玩家必须是 user 或 aura")
    if player == "user" and not client_move_id:
        raise BashRuleError("用户行动缺少 client_move_id")
    if player == "aura" and client_move_id is not None:
        raise BashRuleError("Aura 行动不能使用用户幂等键")

    before = game.remaining_stones
    after = apply_take(before, take_count, game.max_take)
    move = BashGameMove(
        session_id=game.id,
        turn_no=turn_no,
        player=player,
        take_count=take_count,
        remaining_before=before,
        remaining_after=after,
        strategy=strategy,
        client_move_id=client_move_id,
    )
    game.remaining_stones = after
    if after == 0:
        game.status = "finished"
        game.winner = player
        game.current_player = None
        game.finished_at = datetime.now(UTC)
    else:
        game.current_player = "aura" if player == "user" else "user"
    return move


def record_aura_move(game: BashGameSession, *, turn_no: int) -> BashGameMove:
    """为当前 Aura 回合计算确定性策略并更新会话。

    Args:
        game: 当前玩家必须为 ``aura`` 的活动会话实体。
        turn_no: 即将写入的行动序号。

    Returns:
        已应用到 ``game``、但尚未写入数据库的 Aura Move。

    Raises:
        BashGameServiceError: 当前不是 Aura 回合。
    """

    if game.status != "active" or game.current_player != "aura":
        raise BashGameServiceError("当前局面不允许 Aura 行动", status_code=409)
    decision = choose_aura_take(
        game.remaining_stones,
        game.max_take,
        game.difficulty,
        decision_key=f"{game.id}:{game.version}:{turn_no}",
    )
    return record_move(
        game,
        turn_no=turn_no,
        player="aura",
        take_count=decision.take_count,
        client_move_id=None,
        strategy=decision.strategy,
    )


async def list_bash_game_moves(
    session: AsyncSession,
    user_id: str,
    session_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """按行动顺序返回属于当前用户的一局游戏日志。

    查询会先验证棋局所有权，``limit`` 在服务层限制到 1 至 500，防止意外读取
    无界结果。
    """

    game = await get_bash_game(session, user_id, session_id)
    result = await session.execute(
        select(BashGameMove)
        .where(BashGameMove.session_id == game.id)
        .order_by(BashGameMove.turn_no.asc())
        .limit(max(1, min(limit, 500)))
    )
    return [bash_move_dict(move) for move in result.scalars().all()]


async def build_bash_game_snapshot(
    session: AsyncSession,
    game: BashGameSession,
    *,
    action: str,
    new_moves: list[BashGameMove] | None = None,
    idempotent_replay: bool = False,
) -> dict[str, Any]:
    """将 ORM 会话和最近行动转换为稳定的 API/SSE 棋局快照。

    Args:
        session: 用于补充查询最近行动的数据库会话。
        game: 要序列化的会话实体。
        action: 产生快照的业务动作，例如 ``started`` 或 ``moved``。
        new_moves: 当前事务新写入的行动；用于让文案准确描述本轮双方动作。
        idempotent_replay: 当前结果是否来自重复请求。

    Returns:
        使用 camelCase 字段的可 JSON 序列化字典。
    """

    recent_result = await session.execute(
        select(BashGameMove)
        .where(BashGameMove.session_id == game.id)
        .order_by(BashGameMove.turn_no.desc())
        .limit(10)
    )
    recent_moves = list(reversed(recent_result.scalars().all()))
    return {
        "action": action,
        "idempotentReplay": idempotent_replay,
        "game": bash_game_dict(game),
        "newMoves": [bash_move_dict(move) for move in (new_moves or [])],
        "recentMoves": [bash_move_dict(move) for move in recent_moves],
    }


def bash_game_dict(game: BashGameSession) -> dict[str, Any]:
    """把巴什会话实体转换为不暴露内部 ORM 状态的公开字典。"""

    return {
        "id": str(game.id),
        "initialStones": game.initial_stones,
        "remainingStones": game.remaining_stones,
        "maxTake": game.max_take,
        "firstPlayer": game.first_player,
        "currentPlayer": game.current_player,
        "difficulty": game.difficulty,
        "status": game.status,
        "winner": game.winner,
        "version": game.version,
        "createdAt": game.created_at.isoformat() if game.created_at else None,
        "updatedAt": game.updated_at.isoformat() if game.updated_at else None,
        "finishedAt": game.finished_at.isoformat() if game.finished_at else None,
    }


def bash_move_dict(move: BashGameMove) -> dict[str, Any]:
    """把不可变行动实体转换为 API/SSE 使用的公开字典。"""

    return {
        "id": str(move.id) if move.id else None,
        "turnNo": move.turn_no,
        "player": move.player,
        "takeCount": move.take_count,
        "remainingBefore": move.remaining_before,
        "remainingAfter": move.remaining_after,
        "strategy": move.strategy,
        "createdAt": move.created_at.isoformat() if move.created_at else None,
    }
