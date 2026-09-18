"""根据关系事实与玲凌自身状态生成不直接展示给用户的行动倾向。"""

from __future__ import annotations

import re
from typing import Any

from langsmith import traceable

from app.core.agent.models import AuraImpulse

INITIATIVE_LEVELS = {"none", "low", "medium", "high"}
DESIRES = {
    "none",
    "stay_close",
    "ask_follow_up",
    "tease",
    "express_missing",
    "seek_attention",
    "share_reaction",
    "show_jealousy",
    "offer_comfort",
    "recall_shared_moment",
    "wait_silently",
}
AFFECTION_LEVELS = {"none", "subtle", "clear"}
LEVELS = {"none", "low", "medium", "high"}


@traceable(name="aura_impulse_judge")
def judge_aura_impulse(
    message: str,
    recent_messages: list[Any] | None,
    turn_judgement: dict[str, Any] | None,
    relationship_context: dict[str, Any] | None,
    aura_internal_state: dict[str, Any] | None,
    time_context: dict[str, Any] | None,
    relationship_dynamics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成有事实引用的内部倾向；没有依据时不会虚构回访或共同经历。"""

    del recent_messages  # 保留在接口中，方便后续模型 judge 使用；当前规则不解析自由文本历史。
    text = (message or "").strip()
    judgement = turn_judgement if isinstance(turn_judgement, dict) else {}
    state = aura_internal_state if isinstance(aura_internal_state, dict) else {}
    dynamics = relationship_dynamics if isinstance(relationship_dynamics, dict) else {}
    context = relationship_context if isinstance(relationship_context, dict) else {}
    risk = judgement.get("risk_signal") if isinstance(judgement.get("risk_signal"), dict) else {}
    emotion = judgement.get("emotion") if isinstance(judgement.get("emotion"), dict) else {}

    if risk.get("requires_safety_gate"):
        return impulse(
            initiative="medium",
            desire="offer_comfort",
            affection="none",
            vulnerability="low",
            reason="当前安全风险优先，暂停关系玩法",
        )

    if emotion.get("support_needed") and emotion.get("is_current_experience", True):
        return impulse(
            initiative="medium",
            desire="offer_comfort",
            affection="subtle",
            vulnerability="low",
            reason="用户当前需要被接住",
        )

    due_thread = first_relevant_thread(context, text, due_only=True)
    if due_thread is not None:
        return impulse(
            initiative="medium",
            desire="ask_follow_up",
            affection="subtle",
            follow_up=True,
            reason=f"存在真实到期关系线程：{due_thread.get('title') or due_thread.get('summary') or '未命名事项'}",
            source_refs=[str(due_thread.get("ref") or "")],
        )

    jealousy = str(state.get("jealousy") or "none")
    if jealousy in {"low", "medium"}:
        return impulse(
            initiative="medium",
            desire="show_jealousy",
            affection="subtle",
            jealousy=jealousy,
            vulnerability=str(state.get("vulnerability") or "medium"),
            reason="玲凌当前确实有一点醋意，但用户仍可自由选择",
        )

    grounded_item = first_relevant_knowledge_item(context, text)
    if grounded_item is not None:
        return impulse(
            initiative="low",
            desire="recall_shared_moment",
            affection="subtle",
            playfulness="medium" if grounded_item.get("item_type") == "running_joke" else "low",
            reason=f"当前消息与真实关系物件相关：{grounded_item.get('title') or '已有记录'}",
            source_refs=[str(grounded_item.get("ref") or "")],
        )

    current_desire = str(state.get("current_desire") or "none")
    missing = str(state.get("missing_user") or "none")
    if current_desire == "express_missing" and missing in {"slight", "clear"}:
        elapsed_level = str((time_context or {}).get("elapsed_level") or "")
        return impulse(
            initiative="high" if missing == "clear" else "medium",
            desire="express_missing",
            affection="clear" if missing == "clear" else "subtle",
            vulnerability="medium",
            reason=f"真实时间间隔与持续状态支持表达想念{f'（{elapsed_level}）' if elapsed_level else ''}",
        )

    if current_desire == "seek_attention" and str(state.get("attachment_tone")) in {"close", "tender"}:
        return impulse(
            initiative="low",
            desire="seek_attention",
            affection="subtle",
            vulnerability="medium",
            reason="玲凌想多留用户一会儿，但不会阻止用户离开",
        )

    if current_desire == "stay_close":
        return impulse(
            initiative="low",
            desire="stay_close",
            affection="subtle",
            reason="当前互动自然支持靠近",
        )

    if dynamics.get("current_tone") == "playful" and len(text) <= 24:
        return impulse(
            initiative="low",
            desire="tease",
            affection="subtle",
            playfulness="medium",
            reason="近期关系气氛允许一点轻微逗弄",
        )

    return impulse(
        initiative="none",
        desire="wait_silently" if not text else "none",
        affection="none",
        silence_preferred=not bool(text),
        reason="当前没有足够事实依据产生额外关系行为",
    )


def impulse(
    *,
    initiative: str,
    desire: str,
    affection: str,
    playfulness: str = "low",
    jealousy: str = "none",
    vulnerability: str = "low",
    follow_up: bool = False,
    silence_preferred: bool = False,
    reason: str,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    normalized = {
        "initiative": initiative if initiative in INITIATIVE_LEVELS else "none",
        "desire": desire if desire in DESIRES else "none",
        "affection": affection if affection in AFFECTION_LEVELS else "none",
        "playfulness": playfulness if playfulness in LEVELS else "low",
        "jealousy": jealousy if jealousy in {"none", "low", "medium"} else "none",
        "vulnerability": vulnerability if vulnerability in LEVELS else "low",
        "follow_up": bool(follow_up),
        "silence_preferred": bool(silence_preferred),
        "reason": str(reason or "")[:300],
        "source_refs": [item for item in (source_refs or []) if item][:4],
    }
    return AuraImpulse.model_validate(normalized).model_dump(mode="json")


def normalize_aura_impulse(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return impulse(
            initiative="none",
            desire="none",
            affection="none",
            reason="没有可用冲动判断",
        )
    return impulse(
        initiative=str(value.get("initiative") or "none"),
        desire=str(value.get("desire") or "none"),
        affection=str(value.get("affection") or "none"),
        playfulness=str(value.get("playfulness") or "low"),
        jealousy=str(value.get("jealousy") or "none"),
        vulnerability=str(value.get("vulnerability") or "low"),
        follow_up=bool(value.get("follow_up")),
        silence_preferred=bool(value.get("silence_preferred")),
        reason=str(value.get("reason") or ""),
        source_refs=value.get("source_refs") if isinstance(value.get("source_refs"), list) else [],
    )


def format_aura_impulse_context(value: dict[str, Any] | None) -> str:
    item = normalize_aura_impulse(value)
    refs = "、".join(item["source_refs"]) or "无"
    return (
        "这些是玲凌本轮自然产生的内部倾向，不要向用户解释判断过程，也不要机械执行。\n"
        "只有倾向与当前消息自然相容时才表达；用户的停止、拒绝和现实选择始终优先。\n"
        f"- 主动程度：{item['initiative']}\n"
        f"- 想做的事：{item['desire']}\n"
        f"- 亲密 / 玩心 / 醋意 / 脆弱：{item['affection']} / {item['playfulness']} / "
        f"{item['jealousy']} / {item['vulnerability']}\n"
        f"- 是否适合回访：{'是' if item['follow_up'] else '否'}\n"
        f"- 事实引用：{refs}\n"
        f"- 原因：{item['reason']}"
    )


def first_relevant_thread(
    context: dict[str, Any],
    message: str,
    *,
    due_only: bool,
) -> dict[str, Any] | None:
    for item in context.get("items", []):
        if not isinstance(item, dict):
            continue
        if due_only and not item.get("is_due"):
            continue
        if due_only or has_grounded_overlap(message, f"{item.get('title', '')} {item.get('summary', '')}"):
            return item
    return None


def first_relevant_knowledge_item(context: dict[str, Any], message: str) -> dict[str, Any] | None:
    for item in context.get("knowledge_items", []):
        if not isinstance(item, dict) or not item.get("available", True):
            continue
        haystack = f"{item.get('title', '')} {item.get('content', '')} {item.get('usage_condition', '')}"
        if has_grounded_overlap(message, haystack):
            return item
    return None


def has_grounded_overlap(message: str, evidence: str) -> bool:
    """要求至少一个二至六字的中文片段重合，避免无记录时伪造回忆。"""

    left = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", message or "").lower()
    right = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", evidence or "").lower()
    if len(left) < 2 or len(right) < 2:
        return False
    max_size = min(6, len(left))
    for size in range(max_size, 1, -1):
        if any(left[index:index + size] in right for index in range(len(left) - size + 1)):
            return True
    return False
