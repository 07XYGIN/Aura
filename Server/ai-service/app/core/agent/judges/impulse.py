"""Resolve grounded candidate impulses into at most one expression tendency."""

from __future__ import annotations

import re
from typing import Any

from langsmith import traceable

from app.core.agent.models import AuraImpulse, ImpulseCandidate

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
IMPULSE_MIN_SCORE = 65.0


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
    """Collect independent candidates, then select zero or one of them."""

    candidates = collect_impulse_candidates(
        message,
        recent_messages,
        turn_judgement,
        relationship_context,
        aura_internal_state,
        time_context,
        relationship_dynamics,
    )
    return resolve_impulse_candidates(candidates)


def collect_impulse_candidates(
    message: str,
    recent_messages: list[Any] | None,
    turn_judgement: dict[str, Any] | None,
    relationship_context: dict[str, Any] | None,
    aura_internal_state: dict[str, Any] | None,
    time_context: dict[str, Any] | None,
    relationship_dynamics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build grounded options without allowing the first rule to win automatically."""

    text = (message or "").strip()
    judgement = turn_judgement if isinstance(turn_judgement, dict) else {}
    state = aura_internal_state if isinstance(aura_internal_state, dict) else {}
    dynamics = relationship_dynamics if isinstance(relationship_dynamics, dict) else {}
    context = relationship_context if isinstance(relationship_context, dict) else {}
    risk = judgement.get("risk_signal") if isinstance(judgement.get("risk_signal"), dict) else {}
    emotion = judgement.get("emotion") if isinstance(judgement.get("emotion"), dict) else {}
    candidates: list[dict[str, Any]] = []

    if risk.get("requires_safety_gate"):
        return [
            candidate(
                strength="high",
                desire="offer_comfort",
                source="safety_gate",
                affection="none",
                vulnerability="low",
                relevance=100,
                freshness=100,
                reason="当前安全风险优先，暂停关系表达",
            )
        ]

    if emotion.get("support_needed") and emotion.get("is_current_experience", True):
        candidates.append(
            candidate(
                strength="high",
                desire="offer_comfort",
                source="current_emotion",
                affection="subtle",
                vulnerability="low",
                relevance=95,
                freshness=90,
                reason="用户当前需要被接住",
            )
        )

    due_thread = first_relevant_thread(context, text, due_only=True)
    if due_thread is not None:
        overlap = has_grounded_overlap(
            text,
            f"{due_thread.get('title', '')} {due_thread.get('summary', '')}",
        )
        candidates.append(
            candidate(
                strength="medium",
                desire="ask_follow_up",
                source="relationship_thread",
                affection="subtle",
                follow_up=True,
                relevance=85 if overlap else 55,
                freshness=80,
                interrupt_risk=10 if overlap else 35,
                reason=(
                    "存在真实到期关系线程："
                    f"{due_thread.get('title') or due_thread.get('summary') or '未命名事项'}"
                ),
                source_refs=[str(due_thread.get("ref") or "")],
            )
        )

    jealousy = str(state.get("jealousy") or "none")
    if jealousy in {"low", "medium"}:
        active_affects = state.get("active_affects") if isinstance(state.get("active_affects"), list) else []
        jealousy_affect = next(
            (
                item
                for item in active_affects
                if isinstance(item, dict) and item.get("kind") == "jealousy"
            ),
            {},
        )
        candidates.append(
            candidate(
                strength="medium" if jealousy_affect.get("decay_phase") != "fading" else "low",
                desire="show_jealousy",
                source="current_affect",
                affection="subtle",
                jealousy=jealousy,
                vulnerability=str(state.get("vulnerability") or "medium"),
                relevance=85 if len(text) <= 16 else 45,
                freshness=35 if recently_expressed(recent_messages, "show_jealousy") else 80,
                interrupt_risk=25,
                reason="玲凌当前确实有一点醋意，但用户仍可自由选择",
            )
        )

    grounded_item = first_relevant_knowledge_item(context, text)
    if grounded_item is not None:
        candidates.append(
            candidate(
                strength="low",
                desire="recall_shared_moment",
                source="relationship_knowledge",
                affection="subtle",
                playfulness=(
                    "medium" if grounded_item.get("item_type") == "running_joke" else "low"
                ),
                relevance=90,
                freshness=75,
                reason=(
                    "当前消息与真实关系物件相关："
                    f"{grounded_item.get('title') or '已有记录'}"
                ),
                source_refs=[str(grounded_item.get("ref") or "")],
            )
        )

    current_desire = str(state.get("current_desire") or "none")
    missing = str(state.get("missing_user") or "none")
    if current_desire == "express_missing" and missing in {"slight", "clear"}:
        elapsed_level = str((time_context or {}).get("elapsed_level") or "")
        candidates.append(
            candidate(
                strength="high" if missing == "clear" else "medium",
                desire="express_missing",
                source="presence_gap",
                affection="clear" if missing == "clear" else "subtle",
                vulnerability="medium",
                relevance=80,
                freshness=30 if recently_expressed(recent_messages, "express_missing") else 90,
                interrupt_risk=10,
                reason=(
                    "真实时间间隔与持续状态支持表达想念"
                    f"{f'（{elapsed_level}）' if elapsed_level else ''}"
                ),
            )
        )

    if current_desire == "seek_attention" and str(state.get("attachment_tone")) in {"close", "tender"}:
        candidates.append(
            candidate(
                strength="low",
                desire="seek_attention",
                source="leaving_signal",
                affection="subtle",
                vulnerability="medium",
                relevance=80,
                freshness=70,
                interrupt_risk=30,
                reason="玲凌想多留用户一会儿，但不会阻止用户离开",
            )
        )

    if current_desire == "stay_close":
        candidates.append(
            candidate(
                strength="low",
                desire="stay_close",
                source="current_interaction",
                affection="subtle",
                relevance=80,
                freshness=70,
                interrupt_risk=5,
                reason="当前互动自然支持靠近",
            )
        )

    if dynamics.get("relationship_tone") == "playful" and len(text) <= 24:
        candidates.append(
            candidate(
                strength="low",
                desire="tease",
                source="relationship_tone",
                affection="subtle",
                playfulness="medium",
                relevance=65,
                freshness=30 if recently_expressed(recent_messages, "tease") else 75,
                interrupt_risk=15,
                reason="近期关系语气允许一点轻微逗弄",
            )
        )

    if not text:
        candidates.append(
            candidate(
                strength="low",
                desire="wait_silently",
                source="empty_turn",
                affection="none",
                silence_preferred=True,
                relevance=100,
                freshness=100,
                reason="没有用户内容，保持安静",
            )
        )
    return candidates


def resolve_impulse_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Select the best-fitting candidate, or deliberately select none."""

    if not candidates:
        return no_impulse("当前没有足够事实依据产生额外关系行为")
    strength_score = {"none": 0, "low": 20, "medium": 40, "high": 60}

    def score(item: dict[str, Any]) -> float:
        return (
            strength_score.get(str(item.get("strength") or "none"), 0)
            + int(item.get("relevance") or 0) * 0.5
            + int(item.get("freshness") or 0) * 0.2
            - int(item.get("interrupt_risk") or 0) * 0.5
        )

    selected = max(candidates, key=score)
    if score(selected) < IMPULSE_MIN_SCORE:
        return no_impulse("候选倾向与当前对话不够匹配，选择不额外表达")
    return impulse(
        initiative=str(selected.get("strength") or "none"),
        desire=str(selected.get("desire") or "none"),
        affection=str(selected.get("affection") or "none"),
        playfulness=str(selected.get("playfulness") or "low"),
        jealousy=str(selected.get("jealousy") or "none"),
        vulnerability=str(selected.get("vulnerability") or "low"),
        follow_up=bool(selected.get("follow_up")),
        silence_preferred=bool(selected.get("silence_preferred")),
        reason=str(selected.get("reason") or ""),
        source_refs=(
            selected.get("source_refs")
            if isinstance(selected.get("source_refs"), list)
            else []
        ),
    )


def candidate(
    *,
    strength: str,
    desire: str,
    source: str,
    affection: str,
    playfulness: str = "low",
    jealousy: str = "none",
    vulnerability: str = "low",
    follow_up: bool = False,
    silence_preferred: bool = False,
    relevance: int = 0,
    freshness: int = 50,
    interrupt_risk: int = 0,
    reason: str,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    return ImpulseCandidate.model_validate(
        {
            "strength": strength,
            "desire": desire,
            "source": source,
            "affection": affection,
            "playfulness": playfulness,
            "jealousy": jealousy,
            "vulnerability": vulnerability,
            "follow_up": follow_up,
            "silence_preferred": silence_preferred,
            "relevance": relevance,
            "freshness": freshness,
            "interrupt_risk": interrupt_risk,
            "reason": reason,
            "source_refs": [item for item in (source_refs or []) if item][:4],
        }
    ).model_dump(mode="json")


def no_impulse(reason: str) -> dict[str, Any]:
    return impulse(
        initiative="none",
        desire="none",
        affection="none",
        reason=reason,
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
        return no_impulse("没有可用冲动判断")
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
        "这是候选倾向经适配度、新鲜度和打断风险解析后的唯一结果；none 也是正常结果。\n"
        "不要向用户解释判断过程，也不要机械执行；用户的停止、拒绝和现实选择始终优先。\n"
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


def recently_expressed(recent_messages: list[Any] | None, desire: str) -> bool:
    markers = {
        "show_jealousy": ("吃醋", "不高兴", "还记着", "在意"),
        "express_missing": ("想你", "这么晚", "终于回来"),
        "tease": ("逗你", "笨蛋", "才没有"),
    }
    needles = markers.get(desire, ())
    if not needles:
        return False
    texts: list[str] = []
    for item in (recent_messages or [])[-6:]:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content")
        if isinstance(content, str):
            texts.append(content)
    joined = "\n".join(texts)
    return any(marker in joined for marker in needles)


def has_grounded_overlap(message: str, evidence: str) -> bool:
    """Require a short lexical overlap before recalling a grounded item."""

    left = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", message or "").lower()
    right = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", evidence or "").lower()
    if len(left) < 2 or len(right) < 2:
        return False
    max_size = min(6, len(left))
    for size in range(max_size, 1, -1):
        if any(left[index:index + size] in right for index in range(len(left) - size + 1)):
            return True
    return False
