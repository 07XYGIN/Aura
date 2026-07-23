"""共同宠物的纯状态结算和照顾动作规则。

规则刻意避免惩罚性电子宠物设计：长期离线不会死亡、离家、生病或责怪用户；
饱腹和清洁有安全下限，心情只会在短暂动作状态结束后回到平静。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal

PetAction = Literal["feed", "play", "groom", "bathe", "pet", "sleep"]
SUPPORTED_PET_ACTIONS = {"feed", "play", "groom", "bathe", "pet", "sleep"}
SETTLEMENT_QUANTUM = timedelta(hours=3)
MIN_SATIETY = 35
MIN_CLEANLINESS = 40
BABY_DAYS = 14
YOUNG_DAYS = 60


class PetRuleError(ValueError):
    """表示宠物状态或照顾动作不符合确定性领域规则。"""


@dataclass(frozen=True)
class PetState:
    """规则引擎使用的不可变宠物状态快照。

    所有数值范围均为 0 到 100。时间统一为带时区 UTC；``last_settled_at``
    表示数值衰减已经结算到的位置，短于三小时的余量会保留到下一次结算。
    """

    satiety: int
    energy: int
    cleanliness: int
    mood: str
    current_activity: str
    growth_stage: str
    adopted_at: datetime
    mood_until_at: datetime | None
    activity_ends_at: datetime | None
    last_settled_at: datetime


@dataclass(frozen=True)
class PetSettlement:
    """一次惰性时间结算的结果和成长里程碑。"""

    state: PetState
    changed: bool
    milestones: tuple[str, ...]


@dataclass(frozen=True)
class PetActionOutcome:
    """一次照顾动作产生的新状态和可审计变化摘要。"""

    state: PetState
    changes: dict[str, int | str | None]


def normalize_utc(value: datetime) -> datetime:
    """将日期时间转换为 UTC；无时区值按 UTC 解释。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def clamp_score(value: int, minimum: int = 0, maximum: int = 100) -> int:
    """把宠物数值限制在指定闭区间，默认范围为 0 到 100。"""

    return max(minimum, min(maximum, int(value)))


def growth_stage_for(adopted_at: datetime, now: datetime) -> str:
    """按领养后的自然天数计算成长阶段。

    领养不足 14 天为 ``baby``，14 到 59 天为 ``young``，第 60 天起为
    ``adult``。成年后不再衰老，也不存在死亡阶段。
    """

    age = normalize_utc(now) - normalize_utc(adopted_at)
    age_days = max(0, age.days)
    if age_days < BABY_DAYS:
        return "baby"
    if age_days < YOUNG_DAYS:
        return "young"
    return "adult"


def settle_pet_state(state: PetState, now: datetime) -> PetSettlement:
    """根据真实时间惰性结算宠物状态。

    Args:
        state: 上一次持久化的不可变状态。
        now: 本次结算时间；无时区值按 UTC 处理。

    Returns:
        新状态、是否发生变化和成长阶段里程碑。数值每满三小时结算一次：
        饱腹下降 3、清洁下降 1、精力恢复 2；睡眠状态精力恢复 8。饱腹最低
        35、清洁最低 40，永远不会进入伤害或惩罚区。未满三小时的时间不会
        丢失，``last_settled_at`` 只推进已经消费的完整量子。

    Notes:
        心情和活动到期时回到 ``calm``/``idle``。``now`` 不晚于已结算时间时
        完全幂等，不会倒退状态。
    """

    now_utc = normalize_utc(now)
    last_settled = normalize_utc(state.last_settled_at)
    if now_utc <= last_settled:
        return PetSettlement(state=state, changed=False, milestones=())

    elapsed = now_utc - last_settled
    quantum_count = int(elapsed.total_seconds() // SETTLEMENT_QUANTUM.total_seconds())
    satiety = state.satiety
    cleanliness = state.cleanliness
    energy = state.energy
    settled_until = last_settled
    if quantum_count:
        satiety = max(MIN_SATIETY, state.satiety - quantum_count * 3)
        cleanliness = max(MIN_CLEANLINESS, state.cleanliness - quantum_count)
        recovery = quantum_count * (8 if state.current_activity == "sleeping" else 2)
        energy = clamp_score(state.energy + recovery)
        settled_until = last_settled + SETTLEMENT_QUANTUM * quantum_count

    mood = state.mood
    mood_until = state.mood_until_at
    if mood_until is not None and normalize_utc(mood_until) <= now_utc:
        mood = "calm"
        mood_until = None

    activity = state.current_activity
    activity_ends = state.activity_ends_at
    if activity_ends is not None and normalize_utc(activity_ends) <= now_utc:
        activity = "idle"
        activity_ends = None

    growth_stage = growth_stage_for(state.adopted_at, now_utc)
    milestones = () if growth_stage == state.growth_stage else (growth_stage,)
    settled = replace(
        state,
        satiety=satiety,
        energy=energy,
        cleanliness=cleanliness,
        mood=mood,
        current_activity=activity,
        growth_stage=growth_stage,
        mood_until_at=mood_until,
        activity_ends_at=activity_ends,
        last_settled_at=settled_until,
    )
    return PetSettlement(
        state=settled,
        changed=settled != state,
        milestones=milestones,
    )


def apply_pet_action(state: PetState, action: PetAction, now: datetime) -> PetActionOutcome:
    """对已结算状态应用一次温和照顾动作。

    Args:
        state: 执行动作前、已经完成惰性结算的状态。
        action: ``feed``、``play``、``groom``、``bathe``、``pet`` 或 ``sleep``。
        now: 动作发生时间，统一转换为 UTC。

    Returns:
        新状态以及本动作改变的字段。动作可以覆盖上一项短暂活动，不设置强制
        冷却；即使精力较低也允许轻松玩耍，精力最低保持 10。

    Raises:
        PetRuleError: 动作名称不受支持。
    """

    if action not in SUPPORTED_PET_ACTIONS:
        raise PetRuleError("宠物动作必须是 feed、play、groom、bathe、pet 或 sleep")
    now_utc = normalize_utc(now)
    values: dict[str, object] = {}
    if action == "feed":
        values = {
            "satiety": clamp_score(state.satiety + 18),
            "cleanliness": max(MIN_CLEANLINESS, state.cleanliness - 1),
            "mood": "content",
            "current_activity": "eating",
            "mood_until_at": now_utc + timedelta(hours=2),
            "activity_ends_at": now_utc + timedelta(minutes=20),
        }
    elif action == "play":
        values = {
            "satiety": max(MIN_SATIETY, state.satiety - 2),
            "energy": max(10, state.energy - 12),
            "cleanliness": max(MIN_CLEANLINESS, state.cleanliness - 4),
            "mood": "playful",
            "current_activity": "playing",
            "mood_until_at": now_utc + timedelta(hours=2),
            "activity_ends_at": now_utc + timedelta(minutes=30),
        }
    elif action == "groom":
        values = {
            "cleanliness": clamp_score(state.cleanliness + 15),
            "mood": "content",
            "current_activity": "grooming",
            "mood_until_at": now_utc + timedelta(hours=1),
            "activity_ends_at": now_utc + timedelta(minutes=15),
        }
    elif action == "bathe":
        values = {
            "cleanliness": 100,
            "energy": max(10, state.energy - 3),
            "mood": "curious",
            "current_activity": "bathing",
            "mood_until_at": now_utc + timedelta(minutes=45),
            "activity_ends_at": now_utc + timedelta(minutes=20),
        }
    elif action == "pet":
        values = {
            "energy": clamp_score(state.energy + 2),
            "mood": "content",
            "current_activity": "cuddling",
            "mood_until_at": now_utc + timedelta(hours=1),
            "activity_ends_at": now_utc + timedelta(minutes=20),
        }
    elif action == "sleep":
        values = {
            "energy": clamp_score(state.energy + 20),
            "mood": "sleepy",
            "current_activity": "sleeping",
            "mood_until_at": now_utc + timedelta(hours=2),
            "activity_ends_at": now_utc + timedelta(hours=8),
        }

    next_state = replace(state, **values)
    changes = {
        key: getattr(next_state, key)
        for key in values
        if getattr(state, key) != getattr(next_state, key)
    }
    return PetActionOutcome(state=next_state, changes=changes)


def pet_state_dict(state: PetState) -> dict[str, int | str | None]:
    """把规则状态转换为 JSON 可序列化字典，时间字段使用 ISO 8601。"""

    data = asdict(state)
    for key in ("adopted_at", "mood_until_at", "activity_ends_at", "last_settled_at"):
        value = data.get(key)
        data[key] = value.isoformat() if isinstance(value, datetime) else None
    return data


def natural_pet_status(state: PetState) -> dict[str, str]:
    """把内部数值转换为不带分数和惩罚意味的自然状态标签。"""

    satiety = "吃得很饱" if state.satiety >= 80 else "不太需要加餐" if state.satiety >= 55 else "可以吃点东西"
    energy = "精神很好" if state.energy >= 75 else "状态放松" if state.energy >= 40 else "有点困了"
    cleanliness = "毛发很整洁" if state.cleanliness >= 75 else "看起来还算干净" if state.cleanliness >= 55 else "可以梳洗一下"
    return {
        "satiety": satiety,
        "energy": energy,
        "cleanliness": cleanliness,
        "mood": state.mood,
        "activity": state.current_activity,
        "growthStage": state.growth_stage,
    }
