"""关系知识候选的白名单校验与本地兜底识别。

本模块不访问数据库，也不调用模型。记忆裁判可以一次返回向量记忆、关系线程、
关系物件和章节候选；这里负责把后两类候选压缩成服务层能够安全持久化的结构。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import UUID

SUPPORTED_ITEM_OPERATIONS = {"upsert", "deactivate"}
SUPPORTED_ITEM_TYPES = {
    "shared_memory",
    "nickname",
    "running_joke",
    "codeword",
    "ritual",
    "shared_object",
    "action_style",
    "aura_stance",
    "interaction_rule",
    "boundary",
}
SUPPORTED_PERSPECTIVES = {"user", "aura", "shared"}
SUPPORTED_WORLD_LAYERS = {"reality", "shared_history", "imagined", "wish", "promise"}
COOLDOWN_ITEM_TYPES = {"nickname", "running_joke", "codeword", "ritual", "shared_object"}
MAX_ITEM_CANDIDATES = 5
MAX_PRIVATE_PHRASES = 5
KNOWLEDGE_EXTRACTOR_VERSION = "relationship-knowledge-v1"


def normalize_relationship_item_candidates(
    raw_value: Any,
    source_text: str,
    *,
    recent_context: str = "",
) -> list[dict[str, Any]]:
    """校验模型返回的关系物件候选，并去掉没有原文依据的内容。

    Args:
        raw_value: 候选列表，或包含 ``relationship_items`` 的模型 JSON 对象。
        source_text: 当前用户原文，是最优先的证据来源。
        recent_context: 已经真实存在的近期对话文本，可用于确认 Aura 立场或共同经历。

    Returns:
        最多五个字段稳定的候选。新建候选带服务端生成的 ``item_key``；更新或
        停用候选必须带已有对象 UUID。任何自由文本都只会作为数据保存，不能形成
        SQL、工具调用或定时任务。
    """

    raw_items = parse_candidate_list(raw_value, "relationship_items")
    evidence_corpus = f"{source_text}\n{recent_context}".strip()
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_items[: MAX_ITEM_CANDIDATES * 2]:
        if not isinstance(raw, dict):
            continue
        operation = clean_text(raw.get("operation"), 16)
        if operation not in SUPPORTED_ITEM_OPERATIONS:
            continue

        target_id = normalize_optional_uuid(raw.get("target_id") or raw.get("targetId"))
        if operation == "deactivate":
            if not target_id:
                continue
            candidate = {"operation": operation, "target_id": target_id}
            key = (operation, target_id)
            if key not in seen:
                candidates.append(candidate)
                seen.add(key)
            continue

        item_type = clean_text(raw.get("item_type") or raw.get("itemType"), 32)
        perspective = clean_text(raw.get("perspective"), 16)
        world_layer = clean_text(raw.get("world_layer") or raw.get("worldLayer"), 24)
        title = clean_text(raw.get("title"), 160)
        content = clean_text(raw.get("content"), 1200)
        evidence = clean_text(raw.get("evidence"), 240)
        if (
            item_type not in SUPPORTED_ITEM_TYPES
            or perspective not in SUPPORTED_PERSPECTIVES
            or world_layer not in SUPPORTED_WORLD_LAYERS
            or not title
            or not content
            or not evidence
            or not evidence_is_present(evidence, evidence_corpus)
        ):
            continue

        confidence = clamp_float(raw.get("confidence"), 0.0)
        if confidence < 0.6:
            continue
        cooldown_days = normalize_cooldown_days(raw.get("cooldown_days"), item_type)
        item_key = build_item_key(item_type, perspective, title)
        phrases = normalize_phrases(raw.get("phrases"), evidence_corpus)
        candidate = {
            "operation": "upsert",
            "target_id": target_id,
            "item_type": item_type,
            "perspective": perspective,
            "world_layer": world_layer,
            "item_key": item_key,
            "title": title,
            "content": content,
            "usage_condition": clean_text(
                raw.get("usage_condition") or raw.get("usageCondition"),
                400,
            ),
            "confidence": round(confidence, 3),
            "can_change": as_bool(raw.get("can_change", raw.get("canChange", True))),
            "cooldown_days": cooldown_days,
            "phrases": phrases,
            "evidence": evidence,
            "extractor_version": KNOWLEDGE_EXTRACTOR_VERSION,
            "metadata": {
                "phrases": phrases,
                "evidence": evidence,
                "extractor_version": KNOWLEDGE_EXTRACTOR_VERSION,
            },
        }
        key = ("upsert", target_id or item_key)
        if key in seen:
            continue
        candidates.append(candidate)
        seen.add(key)
        if len(candidates) >= MAX_ITEM_CANDIDATES:
            break
    return candidates


def normalize_relationship_chapter_candidate(
    raw_value: Any,
    source_text: str,
    *,
    recent_context: str = "",
) -> dict[str, Any] | None:
    """只保留真正代表关系阶段变化、且能在真实对话中找到证据的章节候选。

    章节是低频时间线，不用于保存普通事件。调用方仍需用稳定消息 ID 构造
    ``source_key``，服务层会在同一事务中关闭旧章节并开启新章节。
    """

    raw = raw_value
    if isinstance(raw_value, dict) and "relationship_chapter" in raw_value:
        raw = raw_value.get("relationship_chapter")
    if not isinstance(raw, dict) or not as_bool(raw.get("create")):
        return None

    title = clean_text(raw.get("title"), 160)
    summary = clean_text(raw.get("summary"), 1200)
    evidence = clean_text(raw.get("evidence"), 300)
    world_layer = clean_text(raw.get("world_layer") or raw.get("worldLayer"), 24)
    importance = clamp_float(raw.get("importance"), 0.0)
    confidence = clamp_float(raw.get("confidence"), 0.0)
    evidence_corpus = f"{source_text}\n{recent_context}".strip()
    if (
        not title
        or not summary
        or not evidence
        or world_layer not in {"reality", "shared_history"}
        or importance < 0.8
        or confidence < 0.75
        or not evidence_is_present(evidence, evidence_corpus)
    ):
        return None
    metadata = {
        "world_layer": world_layer,
        "importance": round(importance, 3),
        "confidence": round(confidence, 3),
        "evidence": evidence,
        "representative_excerpt": clean_text(source_text, 400),
        "extractor_version": KNOWLEDGE_EXTRACTOR_VERSION,
    }
    return {
        "title": title,
        "summary": summary,
        "world_layer": world_layer,
        "importance": round(importance, 3),
        "confidence": round(confidence, 3),
        "evidence": evidence,
        "representative_excerpt": clean_text(source_text, 400),
        "extractor_version": KNOWLEDGE_EXTRACTOR_VERSION,
        "metadata": metadata,
    }


def deterministic_relationship_item_hints(message: str) -> list[dict[str, Any]]:
    """在模型不可用时识别少量明确的说话方式纠偏和称呼约定。

    兜底规则只处理用户直接说出的偏好，不猜测隐含含义。返回值与规范化后的模型
    候选保持同一结构，因此可以走完全相同的数据库服务和幂等边界。
    """

    text = (message or "").strip()
    if not text:
        return []
    hints: list[dict[str, Any]] = []
    if ("太客服" in text or "像客服" in text) and not is_denied_or_example(
        text,
        r"(?:太|像)客服",
    ):
        hints.append(
            deterministic_item(
                "action_style",
                "避免客服式表达",
                "小乔不喜欢客服式、模板化的承接；优先像熟悉的恋人一样直接接话。",
                text,
            )
        )
    if (
        re.search(r"(?:别|不要).{0,8}(?:每次|总是).{0,8}安慰", text)
        and not is_denied_or_example(text, r"(?:别|不要).{0,8}(?:每次|总是).{0,8}安慰")
    ):
        hints.append(
            deterministic_item(
                "boundary",
                "不要机械安慰",
                "小乔表达疲惫或抱怨时，不要立刻进入安慰和建议模式；先自然接话，除非他明确求助。",
                text,
            )
        )
    if "太长了" in text and any(marker in text for marker in ("回复", "这句", "说话", "你")):
        hints.append(
            deterministic_item(
                "action_style",
                "回复不要过长",
                "普通闲聊优先短而自然；需要方案或分析时再完整展开。",
                text,
            )
        )
    if "太黏" in text:
        hints.append(
            deterministic_item(
                "boundary",
                "亲密表达不要太黏",
                "亲密可以主动，但不要每轮都黏着、索取回应或把气氛填满。",
                text,
            )
        )
    nickname_match = re.search(r"(?:以后|之后)?(?:就)?叫我[“\"']?([^，。！？、\s\"'”]{1,12})", text)
    if nickname_match and is_denied_or_example(text, r"(?:以后|之后)?(?:就)?叫我"):
        nickname_match = None
    if nickname_match:
        nickname = nickname_match.group(1)
        hints.append(
            deterministic_item(
                "nickname",
                nickname,
                f"Aura 可以在自然合适的时候称呼小乔为“{nickname}”，但不要每句话重复。",
                nickname,
                cooldown_days=3,
                phrases=[nickname],
            )
        )
    return hints[:MAX_ITEM_CANDIDATES]


def is_denied_or_example(text: str, marker_pattern: str) -> bool:
    """判断一个确定性信号是否只出现在否认、引用或举例语境中。

    该保护只用于本地高置信规则。模型候选仍必须通过逐字 evidence 校验，但本地
    正则没有语义判断能力，因此宁可漏记，也不能把“我没说……”反向保存成偏好。
    """

    denial = rf"(?:没|没有|不是|并不是|并非)(?:说|觉得|认为|要求)?[^。！？]{{0,12}}{marker_pattern}"
    if re.search(denial, text):
        return True
    example_markers = ("只是在举例", "只是举例", "举个例子", "比如说", "假设我说")
    return any(marker in text for marker in example_markers)


def deterministic_item(
    item_type: str,
    title: str,
    content: str,
    evidence: str,
    *,
    cooldown_days: int = 0,
    phrases: list[str] | None = None,
) -> dict[str, Any]:
    """构造一个来自明确本地规则的关系物件候选。"""

    metadata = {
        "phrases": phrases or [],
        "evidence": evidence[:240],
        "extractor_version": f"{KNOWLEDGE_EXTRACTOR_VERSION}:deterministic",
    }
    return {
        "operation": "upsert",
        "target_id": None,
        "item_type": item_type,
        "perspective": "user",
        "world_layer": "reality",
        "item_key": build_item_key(item_type, "user", title),
        "title": title,
        "content": content,
        "usage_condition": None,
        "confidence": 1.0,
        "can_change": True,
        "cooldown_days": cooldown_days,
        "phrases": phrases or [],
        "evidence": evidence[:240],
        "extractor_version": f"{KNOWLEDGE_EXTRACTOR_VERSION}:deterministic",
        "metadata": metadata,
    }


def build_item_key(item_type: str, perspective: str, title: str) -> str:
    """根据受限类型、视角和规范标题生成稳定且不泄露正文的业务键。"""

    normalized_title = re.sub(r"\s+", "", title).casefold()
    digest = hashlib.sha256(
        f"{item_type}|{perspective}|{normalized_title}".encode("utf-8")
    ).hexdigest()[:32]
    return f"knowledge:{item_type}:{digest}"


def parse_candidate_list(raw_value: Any, container_key: str) -> list[Any]:
    """把 JSON 字符串、列表或外层模型对象统一成候选列表。"""

    value = raw_value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, dict):
        value = value.get(container_key, [])
    return value if isinstance(value, list) else []


def normalize_optional_uuid(value: Any) -> str | None:
    """规范可选 UUID；模型伪造的普通字符串不会进入数据库查询。"""

    if value is None:
        return None
    try:
        return str(UUID(str(value).strip()))
    except (TypeError, ValueError):
        return None


def evidence_is_present(evidence: str, corpus: str) -> bool:
    """确认模型给出的短证据确实存在于当前或近期真实对话。"""

    normalized_evidence = re.sub(r"\s+", "", evidence).casefold()
    normalized_corpus = re.sub(r"\s+", "", corpus).casefold()
    return bool(normalized_evidence and normalized_evidence in normalized_corpus)


def normalize_phrases(value: Any, evidence_corpus: str) -> list[str]:
    """只保留真实出现过的私人短语，供后续本地冷却回写使用。"""

    if not isinstance(value, list):
        return []
    phrases: list[str] = []
    seen: set[str] = set()
    for raw in value[: MAX_PRIVATE_PHRASES * 2]:
        phrase = clean_text(raw, 40)
        if not phrase or not evidence_is_present(phrase, evidence_corpus):
            continue
        key = phrase.casefold()
        if key not in seen:
            phrases.append(phrase)
            seen.add(key)
        if len(phrases) >= MAX_PRIVATE_PHRASES:
            break
    return phrases


def normalize_cooldown_days(value: Any, item_type: str) -> int:
    """把复用冷却限制在 0-3650 天；只有私人语言类默认需要冷却。"""

    default = 14 if item_type in COOLDOWN_ITEM_TYPES else 0
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return max(0, min(result, 3650))


def clean_text(value: Any, max_length: int) -> str | None:
    """去掉空白并限制自由文本长度。"""

    if value is None:
        return None
    text = str(value).strip()
    return text[:max_length] if text else None


def clamp_float(value: Any, default: float) -> float:
    """将模型数值限制在 0 到 1。"""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(number, 1.0))


def as_bool(value: Any) -> bool:
    """兼容模型常见的字符串布尔值。"""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)
