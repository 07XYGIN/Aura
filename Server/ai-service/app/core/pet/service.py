"""共同宠物的 PostgreSQL 事务服务。

宠物行保存当前权威状态，PetEvent 保存不可变事实。所有修改操作通过行锁串行化；
重复 ``client_action_id`` 只重放首次事件，不再次结算或执行动作。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CompanionPet, PetEvent, Users
from app.schemas.pet import PetActionRequest, PetAdoptRequest, PetRenameRequest

from .narrator import action_narrative, adoption_narrative, rename_narrative
from .rules import (
    PetRuleError,
    PetState,
    apply_pet_action,
    natural_pet_status,
    pet_state_dict,
    settle_pet_state,
)


class PetServiceError(RuntimeError):
    """可转换为中文 HTTP 或聊天回复的宠物服务异常。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        """保存用户可读错误信息及建议 HTTP 状态码。"""

        super().__init__(message)
        self.status_code = status_code


def parse_pet_user_id(user_id: str) -> UUID:
    """解析宠物所有者 UUID，格式无效时抛出 400 领域异常。"""

    try:
        return UUID(str(user_id))
    except (TypeError, ValueError) as exc:
        raise PetServiceError("用户 ID 无效", status_code=400) from exc


async def get_pet_for_user(
    session: AsyncSession,
    user_id: str,
    *,
    for_update: bool = False,
) -> CompanionPet | None:
    """查询用户唯一的共同宠物。

    Args:
        session: 当前异步数据库会话。
        user_id: 宠物所属用户 UUID 字符串。
        for_update: 为真时对宠物行加 ``FOR UPDATE`` 锁；调用方必须在同一事务
            内完成状态修改与提交。

    Returns:
        ``CompanionPet`` 实体；用户尚未领养时返回 ``None``。
    """

    statement = select(CompanionPet).where(
        CompanionPet.user_id == parse_pet_user_id(user_id)
    )
    if for_update:
        statement = statement.with_for_update()
    result = await session.execute(statement.limit(1))
    return result.scalar_one_or_none()


async def adopt_pet(
    session: AsyncSession,
    user_id: str,
    request: PetAdoptRequest,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """为当前用户幂等领养唯一的共同宠物。

    Args:
        session: 用于行锁、插入事件和提交的异步数据库会话。
        user_id: 从 JWT 或聊天请求取得的当前用户 ID。
        request: 宠物名字、物种、性格和领养请求幂等键。
        now: 可注入的 UTC 时间，主要用于测试；默认当前时间。

    Returns:
        包含宠物公开状态、领养事件和最近事件的快照。

    Raises:
        PetServiceError: 用户不存在、已经领养另一只宠物，或并发创建冲突。

    Side Effects:
        锁定 users 行，新建宠物和 adoption 事件，并在同一事务提交。
    """

    parsed_user_id = parse_pet_user_id(user_id)
    normalized_name = request.name.strip()
    if not normalized_name:
        raise PetServiceError("宠物名字不能为空")

    user_result = await session.execute(
        select(Users.id).where(Users.id == parsed_user_id).with_for_update()
    )
    if user_result.scalar_one_or_none() is None:
        raise PetServiceError("用户不存在", status_code=404)

    existing = await get_pet_for_user(session, user_id)
    if existing is not None:
        replay = await find_pet_event_by_client_id(
            session,
            existing.id,
            request.adoption_request_id,
        )
        if replay is not None:
            ensure_pet_event_replay(
                replay,
                expected_event_type="adoption",
                expected_action="adopt",
                expected_payload={
                    "name": normalized_name,
                    "species": request.species,
                    "personality": request.personality,
                },
            )
            return await build_pet_snapshot(
                session,
                existing,
                action="adoption_replayed",
                event=replay,
                idempotent_replay=True,
            )
        raise PetServiceError("我们已经领养了一只共同宠物", status_code=409)

    occurred_at = now or datetime.now(UTC)
    pet = CompanionPet(
        user_id=parsed_user_id,
        name=normalized_name,
        species=request.species,
        personality=request.personality,
        growth_stage="baby",
        satiety=80,
        energy=80,
        cleanliness=80,
        mood="calm",
        current_activity="idle",
        adopted_at=occurred_at,
        last_settled_at=occurred_at,
        version=1,
        metadata_json={"care_model": "gentle_non_punitive_v1"},
    )
    session.add(pet)
    try:
        await session.flush()
        state_after = pet_state_dict(pet_state_from_model(pet))
        event = PetEvent(
            pet_id=pet.id,
            actor="user",
            event_type="adoption",
            action="adopt",
            state_before={},
            state_after=state_after,
            narrative=adoption_narrative(pet.name, pet.species),
            client_action_id=request.adoption_request_id,
            metadata_json={
                "name": pet.name,
                "species": pet.species,
                "personality": pet.personality,
            },
            occurred_at=occurred_at,
        )
        session.add(event)
        await session.commit()
        await session.refresh(pet)
        await session.refresh(event)
    except IntegrityError as exc:
        await session.rollback()
        raise PetServiceError("领养请求发生并发冲突，请重新读取宠物状态", status_code=409) from exc

    return await build_pet_snapshot(session, pet, action="adopted", event=event)


async def get_pet_snapshot(
    session: AsyncSession,
    user_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """读取宠物并惰性结算到当前时间。

    读取可能推进 ``last_settled_at``、更新自然成长阶段，并写入成长里程碑事件，
    因此会锁定宠物行。没有宠物时返回 ``None``。
    """

    pet = await get_pet_for_user(session, user_id, for_update=True)
    if pet is None:
        return None
    changed, growth_events = settle_pet_model(pet, now or datetime.now(UTC))
    for event in growth_events:
        session.add(event)
    if changed:
        pet.version += 1
        await session.commit()
        await session.refresh(pet)
        for event in growth_events:
            await session.refresh(event)
    return await build_pet_snapshot(
        session,
        pet,
        action="settled" if changed else "status",
        event=growth_events[-1] if growth_events else None,
    )


async def perform_pet_action(
    session: AsyncSession,
    user_id: str,
    request: PetActionRequest,
    *,
    actor: str = "user",
    now: datetime | None = None,
) -> dict[str, Any]:
    """原子结算状态并执行一次宠物照顾动作。

    Args:
        session: 当前异步数据库会话。
        user_id: 宠物所属用户 ID。
        request: 动作名称、幂等 ID 和可选期望版本。
        actor: 事实执行者，允许 ``user`` 或 ``aura``；HTTP/聊天入口固定为 user，
            将来 Aura 自主照顾时必须通过本函数真实落库。
        now: 可注入动作时间，默认当前 UTC 时间。

    Returns:
        动作后的宠物快照与本次不可变事件。重复 ``client_action_id`` 直接重放
        首次事件，不结算时间、不再次修改状态。

    Raises:
        PetServiceError: 尚未领养、版本冲突、执行者无效或动作不受支持。

    Side Effects:
        使用 ``FOR UPDATE`` 锁定宠物，在同一事务更新状态、增加版本并写事件。
    """

    if actor not in {"user", "aura"}:
        raise PetServiceError("宠物动作执行者必须是 user 或 aura")
    pet = await require_locked_pet(session, user_id)
    replay = await find_pet_event_by_client_id(session, pet.id, request.client_action_id)
    if replay is not None:
        ensure_pet_event_replay(
            replay,
            expected_event_type="action",
            expected_action=request.action,
        )
        return await build_pet_snapshot(
            session,
            pet,
            action="action_replayed",
            event=replay,
            idempotent_replay=True,
        )
    ensure_pet_version(pet, request.expected_version)

    occurred_at = now or datetime.now(UTC)
    _settled, growth_events = settle_pet_model(pet, occurred_at)
    for growth_event in growth_events:
        session.add(growth_event)
    before_state = pet_state_from_model(pet)
    try:
        outcome = apply_pet_action(before_state, request.action, occurred_at)
    except PetRuleError as exc:
        raise PetServiceError(str(exc)) from exc
    apply_state_to_model(pet, outcome.state)
    pet.version += 1
    event = PetEvent(
        pet_id=pet.id,
        actor=actor,
        event_type="action",
        action=request.action,
        state_before=pet_state_dict(before_state),
        state_after=pet_state_dict(outcome.state),
        narrative=action_narrative(pet.name, request.action),
        client_action_id=request.client_action_id,
        metadata_json={"changes": serialize_changes(outcome.changes), "pet_version": pet.version},
        occurred_at=occurred_at,
    )
    session.add(event)
    try:
        await session.commit()
        await session.refresh(pet)
        await session.refresh(event)
    except IntegrityError as exc:
        await session.rollback()
        raise PetServiceError("宠物动作发生并发冲突，请刷新状态后重试", status_code=409) from exc
    return await build_pet_snapshot(session, pet, action=request.action, event=event)


async def rename_pet(
    session: AsyncSession,
    user_id: str,
    request: PetRenameRequest,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """幂等修改宠物名字并记录 rename 事件。

    改名不会改变照顾数值和心情。版本冲突返回 409；重复请求 ID 只重放首次
    事件，确保重试不会产生多条改名历史。
    """

    pet = await require_locked_pet(session, user_id)
    new_name = request.name.strip()
    if not new_name:
        raise PetServiceError("宠物名字不能为空")
    replay = await find_pet_event_by_client_id(session, pet.id, request.client_action_id)
    if replay is not None:
        ensure_pet_event_replay(
            replay,
            expected_event_type="rename",
            expected_action="rename",
            expected_payload={"new_name": new_name},
        )
        return await build_pet_snapshot(
            session,
            pet,
            action="rename_replayed",
            event=replay,
            idempotent_replay=True,
        )
    ensure_pet_version(pet, request.expected_version)
    occurred_at = now or datetime.now(UTC)
    _settled, growth_events = settle_pet_model(pet, occurred_at)
    for growth_event in growth_events:
        session.add(growth_event)
    before_state = pet_state_dict(pet_state_from_model(pet))
    old_name = pet.name
    pet.name = new_name
    pet.version += 1
    event = PetEvent(
        pet_id=pet.id,
        actor="user",
        event_type="rename",
        action="rename",
        state_before={**before_state, "name": old_name},
        state_after={**before_state, "name": new_name},
        narrative=rename_narrative(old_name, new_name),
        client_action_id=request.client_action_id,
        metadata_json={"old_name": old_name, "new_name": new_name, "pet_version": pet.version},
        occurred_at=occurred_at,
    )
    session.add(event)
    try:
        await session.commit()
        await session.refresh(pet)
        await session.refresh(event)
    except IntegrityError as exc:
        await session.rollback()
        raise PetServiceError("宠物改名发生并发冲突，请刷新状态后重试", status_code=409) from exc
    return await build_pet_snapshot(session, pet, action="renamed", event=event)


async def list_pet_events(
    session: AsyncSession,
    user_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """按时间倒序读取当前用户宠物的不可变事件。

    尚未领养时返回空列表；``limit`` 在服务层限制为 1 到 200。
    """

    pet = await get_pet_for_user(session, user_id)
    if pet is None:
        return []
    result = await session.execute(
        select(PetEvent)
        .where(PetEvent.pet_id == pet.id)
        .order_by(PetEvent.occurred_at.desc())
        .limit(max(1, min(limit, 200)))
    )
    return [pet_event_dict(event) for event in result.scalars().all()]


async def require_locked_pet(session: AsyncSession, user_id: str) -> CompanionPet:
    """查询并锁定用户宠物，尚未领养时抛出 404 领域异常。"""

    pet = await get_pet_for_user(session, user_id, for_update=True)
    if pet is None:
        raise PetServiceError("我们还没有领养共同宠物", status_code=404)
    return pet


async def find_pet_event_by_client_id(
    session: AsyncSession,
    pet_id: UUID,
    client_action_id: str,
) -> PetEvent | None:
    """按宠物和客户端动作 ID 查询首次事件，用于幂等重放。"""

    result = await session.execute(
        select(PetEvent).where(
            PetEvent.pet_id == pet_id,
            PetEvent.client_action_id == client_action_id,
        )
    )
    return result.scalar_one_or_none()


def ensure_pet_event_replay(
    event: PetEvent,
    *,
    expected_event_type: str,
    expected_action: str,
    expected_payload: dict[str, Any] | None = None,
) -> None:
    """确认重复客户端 ID 确实属于同一种宠物操作。

    Args:
        event: 使用该 ``client_action_id`` 首次写入的事实事件。
        expected_event_type: 当前请求预期的事件类型。
        expected_action: 当前请求预期的具体动作。
        expected_payload: 必须与首次事件 metadata 匹配的原始业务字段，例如领养
            身份或新名字；版本号和时间等非业务字段不参与比较。

    Raises:
        PetServiceError: 同一个客户端 ID 被复用于另一事件类型或动作。此时返回
            409，而不是把错误操作伪装成幂等成功。
    """

    if event.event_type != expected_event_type or event.action != expected_action:
        raise PetServiceError(
            "这个 clientActionId 已经用于另一项宠物操作，请为新操作生成新的 ID",
            status_code=409,
        )
    metadata = event.metadata_json or {}
    if expected_payload and any(metadata.get(key) != value for key, value in expected_payload.items()):
        raise PetServiceError(
            "这个 clientActionId 对应的宠物操作参数不同，请为新请求生成新的 ID",
            status_code=409,
        )


def ensure_pet_version(pet: CompanionPet, expected_version: int | None) -> None:
    """比较可选乐观版本，过期时抛出携带当前版本的 409 异常。"""

    if expected_version is not None and pet.version != expected_version:
        raise PetServiceError(
            f"宠物状态已变化，当前版本是 {pet.version}，请刷新后重试",
            status_code=409,
        )


def settle_pet_model(pet: CompanionPet, now: datetime) -> tuple[bool, list[PetEvent]]:
    """在内存中惰性结算 ORM 宠物，并为成长变化构造系统事件。

    Returns:
        ``(状态是否变化, 尚未写库的成长事件列表)``。普通数值变化不产生事件，
        避免时间衰减淹没真实共同经历；只有成长阶段变化才生成 milestone。

    Side Effects:
        原地更新 ``pet``，但不 flush、不提交；调用方负责事务。
    """

    before = pet_state_from_model(pet)
    settlement = settle_pet_state(before, now)
    if not settlement.changed:
        return False, []
    apply_state_to_model(pet, settlement.state)
    events: list[PetEvent] = []
    for stage in settlement.milestones:
        events.append(
            PetEvent(
                pet_id=pet.id,
                actor="system",
                event_type="growth",
                action="grow",
                state_before=pet_state_dict(before),
                state_after=pet_state_dict(settlement.state),
                narrative=growth_narrative(pet.name, stage),
                client_action_id=None,
                metadata_json={"growth_stage": stage},
                occurred_at=now,
            )
        )
    return True, events


def growth_narrative(name: str, stage: str) -> str:
    """根据已达到的成长阶段生成不包含数值或衰老暗示的里程碑文案。"""

    if stage == "young":
        return f"{name}已经从刚领养时的小不点，长成更有精神的小家伙了。"
    if stage == "adult":
        return f"{name}长大了，熟悉这个家以后，举动也比刚来时从容了不少。"
    return f"{name}进入了新的成长阶段。"


def pet_state_from_model(pet: CompanionPet) -> PetState:
    """把 ORM 宠物转换为规则引擎的不可变状态。"""

    return PetState(
        satiety=pet.satiety,
        energy=pet.energy,
        cleanliness=pet.cleanliness,
        mood=pet.mood,
        current_activity=pet.current_activity,
        growth_stage=pet.growth_stage,
        adopted_at=pet.adopted_at,
        mood_until_at=pet.mood_until_at,
        activity_ends_at=pet.activity_ends_at,
        last_settled_at=pet.last_settled_at,
    )


def apply_state_to_model(pet: CompanionPet, state: PetState) -> None:
    """把规则状态原地写回 ORM 实体；不修改名字、身份、版本和元数据。"""

    pet.satiety = state.satiety
    pet.energy = state.energy
    pet.cleanliness = state.cleanliness
    pet.mood = state.mood
    pet.current_activity = state.current_activity
    pet.growth_stage = state.growth_stage
    pet.mood_until_at = state.mood_until_at
    pet.activity_ends_at = state.activity_ends_at
    pet.last_settled_at = state.last_settled_at


def serialize_changes(changes: dict[str, Any]) -> dict[str, Any]:
    """把动作变化字典中的 datetime 转为 ISO 字符串，供 JSONB 安全保存。"""

    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in changes.items()
    }


async def build_pet_snapshot(
    session: AsyncSession,
    pet: CompanionPet,
    *,
    action: str,
    event: PetEvent | None = None,
    idempotent_replay: bool = False,
) -> dict[str, Any]:
    """把当前宠物、自然状态和最近事件组合为 API/SSE 快照。

    Args:
        session: 用于读取最近事件的数据库会话。
        pet: 当前权威 ORM 状态。
        action: 产生快照的业务动作。
        event: 本轮新写入或幂等重放的事实事件。
        idempotent_replay: 是否来自重复客户端动作 ID。
    """

    recent_result = await session.execute(
        select(PetEvent)
        .where(PetEvent.pet_id == pet.id)
        .order_by(PetEvent.occurred_at.desc())
        .limit(10)
    )
    state = pet_state_from_model(pet)
    natural = natural_pet_status(state)
    return {
        "action": action,
        "idempotentReplay": idempotent_replay,
        "pet": pet_public_dict(pet, state, natural),
        "event": pet_event_dict(event) if event is not None else None,
        "recentEvents": [pet_event_dict(item) for item in recent_result.scalars().all()],
        "statusText": format_pet_status_text(pet.name, natural),
    }


def pet_public_dict(
    pet: CompanionPet,
    state: PetState,
    natural: dict[str, str],
) -> dict[str, Any]:
    """把宠物 ORM 实体转换为包含内部照顾值和自然标签的公开字典。"""

    return {
        "id": str(pet.id),
        "name": pet.name,
        "species": pet.species,
        "personality": pet.personality,
        "growthStage": pet.growth_stage,
        "careState": {
            "satiety": state.satiety,
            "energy": state.energy,
            "cleanliness": state.cleanliness,
        },
        "naturalState": natural,
        "mood": pet.mood,
        "currentActivity": pet.current_activity,
        "version": pet.version,
        "adoptedAt": pet.adopted_at.isoformat(),
        "lastSettledAt": pet.last_settled_at.isoformat(),
        "createdAt": pet.created_at.isoformat() if pet.created_at else None,
        "updatedAt": pet.updated_at.isoformat() if pet.updated_at else None,
    }


def pet_event_dict(event: PetEvent) -> dict[str, Any]:
    """把宠物事实事件转换为 API/SSE 使用的公开字典。"""

    return {
        "id": str(event.id) if event.id else None,
        "actor": event.actor,
        "eventType": event.event_type,
        "action": event.action,
        "stateBefore": event.state_before,
        "stateAfter": event.state_after,
        "narrative": event.narrative,
        "metadata": event.metadata_json or {},
        "occurredAt": event.occurred_at.isoformat() if event.occurred_at else None,
    }


def format_pet_status_text(name: str, natural: dict[str, str]) -> str:
    """用自然标签构造不暴露数值、没有责怪意味的宠物状态说明。"""

    return (
        f"{name}现在{natural['satiety']}，{natural['energy']}，"
        f"{natural['cleanliness']}。当前状态是 {natural['activity']}。"
    )
