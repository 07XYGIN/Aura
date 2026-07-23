"""为普通 Aura 对话提供只读、可核验的宠物上下文。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.models import CompanionPet, PetEvent
from app.db.session import SyncSessionLocal

from .rules import natural_pet_status, settle_pet_state
from .service import pet_state_from_model

NO_PET_CONTEXT = (
    "【共同宠物】\n"
    "目前还没有领养共同宠物。除非小乔正在讨论领养，否则不要假装我们已经养了某只动物，"
    "也不要编造喂食、打翻东西或等待主人等经历。"
)


def load_pet_context_sync(user_id: str, *, event_limit: int = 2) -> str:
    """同步读取并格式化普通聊天所需的宠物上下文。

    Args:
        user_id: 当前 LangGraph 线程对应的用户 UUID。
        event_limit: 最多引用的最近事实事件数量，限制在 0 到 5。

    Returns:
        可直接注入系统提示词的中文片段。没有宠物、ID 无效或数据库读取失败
        时返回明确的“尚未领养”约束。

    Notes:
        本函数只在内存中计算惰性状态，不写数据库。它不能生成新的宠物事实，
        最近经历只来自已经持久化的 ``pet_event``。
    """

    try:
        parsed_user_id = UUID(str(user_id))
    except (TypeError, ValueError):
        return NO_PET_CONTEXT

    try:
        with SyncSessionLocal() as session:
            pet = session.execute(
                select(CompanionPet).where(CompanionPet.user_id == parsed_user_id).limit(1)
            ).scalar_one_or_none()
            if pet is None:
                return NO_PET_CONTEXT
            recent_events = session.execute(
                select(PetEvent)
                .where(PetEvent.pet_id == pet.id)
                .order_by(PetEvent.occurred_at.desc())
                .limit(max(0, min(event_limit, 5)))
            ).scalars().all()
            settled = settle_pet_state(pet_state_from_model(pet), datetime.now(UTC)).state
            natural = natural_pet_status(settled)
            narratives = [event.narrative.strip() for event in recent_events if event.narrative.strip()]
            return format_pet_context(
                name=pet.name,
                species=pet.species,
                personality=pet.personality,
                natural_state=natural,
                recent_narratives=narratives,
            )
    except Exception:
        logging.exception("读取共同宠物上下文失败 user_id=%s", user_id)
        return NO_PET_CONTEXT


def format_pet_context(
    *,
    name: str,
    species: str,
    personality: str,
    natural_state: dict[str, str],
    recent_narratives: list[str],
) -> str:
    """把真实宠物身份、自然状态和近期事件压缩为模型上下文。

    数值分数不会写入提示词，避免模型把照顾状态解释成关系评分。近期经历为空
    时明确说明没有可引用事件，禁止模型自行补全。
    """

    species_names = {"cat": "猫", "dog": "狗", "rabbit": "兔子"}
    personality_names = {
        "gentle": "温和",
        "playful": "活泼",
        "curious": "好奇",
        "quiet": "安静",
    }
    events_text = "；".join(recent_narratives) if recent_narratives else "没有新的已记录事件"
    return (
        "【共同宠物】\n"
        f"我们真实领养的宠物叫{name}，是{personality_names.get(personality, personality)}的"
        f"{species_names.get(species, species)}。\n"
        f"当前自然状态：{natural_state['satiety']}，{natural_state['energy']}，"
        f"{natural_state['cleanliness']}，正在 {natural_state['activity']}。\n"
        f"最近已记录事件：{events_text}。\n"
        "只能引用以上已确认事实；不要虚构它在离线期间等待、挨饿、生病或制造了新事件。"
    )
