"""关系线程候选的保守规范化与本地回退识别。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

SUPPORTED_OPERATIONS = {"create", "update", "resolve", "abandon"}
SUPPORTED_THREAD_TYPES = {"open_item", "follow_up", "conflict", "promise", "project_task"}
SUPPORTED_PERSPECTIVES = {"user", "aura", "shared"}
SUPPORTED_WORLD_LAYERS = {"reality", "shared_history", "imagined", "wish", "promise"}
EXTRACTOR_VERSION = "relationship-thread-v1"
AURA_TIMEZONE = ZoneInfo("Asia/Shanghai")
MAX_THREAD_CANDIDATES = 5

FOLLOW_UP_AUTHORIZATION_PATTERNS = (
    r"记得(?:到时候)?(?:问|提醒)我",
    r"(?:到时候|明天|后天|下次)问我",
    r"提醒我",
    r"别忘了(?:问|提醒)我",
)
FOLLOW_UP_DENIAL_PATTERNS = (
    r"(?:不用|不要|无需|不必|别(?!忘)).{0,6}(?:问|提醒)我",
    r"(?:取消|撤销).{0,6}(?:提醒|跟进)",
    r"(?:别再|不要再)跟进",
)
HYPOTHETICAL_PREFIXES = ("如果", "假如", "要是", "万一", "假设", "比如", "例如")
TRIVIAL_FUTURE_PHRASES = {"明天见", "明天聊", "明天再聊", "下次见", "回头见"}
NEGATED_OPEN_THREAD_PATTERNS = (
    r"(?:明天|后天|周末|下周).{0,12}(?:不用|不要|不需要|取消|不去|不做|不修|不发|不上线)",
    r"(?:不用|不要|不需要|取消).{0,12}(?:面试|发布|上线|修|处理|继续聊)",
)
OPEN_THREAD_PATTERNS = (
    r"(?:明天|后天|周末|下周).{0,20}(?:要|得|准备|面试|发布|上线|修|做|交|去)",
    r"(?:这个|那个|这件).{0,20}(?:下次|之后|回头|周末).{0,12}(?:继续|再|处理|修|聊)",
    r"下次继续.{0,40}",
    r"等.{1,30}(?:到了|结束了|上线了|发布了|修好了|做完了).{0,20}",
)
CONFLICT_PATTERNS = (
    r"你.{0,12}(?:理解错了|又理解错了|在敷衍|太客服|不像她|不懂我)",
    r"(?:别|不要).{0,12}(?:每次|总是).{0,15}(?:安慰|说教|追问|道歉)",
    r"我不是这个意思",
    r"这句话太客服",
)


def normalize_thread_candidates(
    raw_value: Any,
    source_text: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """把模型或规则输出限制为关系线程服务可接受的候选列表。

    Args:
        raw_value: JSON 字符串、候选字典、候选列表，或包含
            ``relationship_threads`` 的记忆判断结果。
        source_text: 用户本轮原文，用于验证主动跟进是否获得明确授权。
        now: 解析无时区时间时使用的基准时刻，默认当前 UTC 时间。

    Returns:
        最多五个字段稳定的候选字典。无效类型、缺少目标 ID 的状态操作、空标题
        或空摘要会被丢弃。``follow_up_at`` 统一为 UTC ISO 字符串。

    Security:
        模型即使返回 ``proactive_allowed=true``，用户原文没有“记得问我”等明确
        授权时也会被强制改为 ``False``，自动识别事项本身不会擅自建立提醒。
    """

    parsed = parse_candidate_container(raw_value)
    normalized: list[dict[str, Any]] = []
    reference_now = normalize_datetime(now or datetime.now(UTC))
    authorized = has_explicit_follow_up_authorization(source_text)
    denies_new_thread = any(
        re.search(pattern, source_text)
        for pattern in (*FOLLOW_UP_DENIAL_PATTERNS, *NEGATED_OPEN_THREAD_PATTERNS)
    )

    for raw in parsed[:MAX_THREAD_CANDIDATES]:
        if not isinstance(raw, dict):
            continue
        operation_value = str(raw.get("operation") or "create").strip().lower()
        thread_type_value = str(raw.get("thread_type") or "").strip().lower()
        if operation_value not in SUPPORTED_OPERATIONS or thread_type_value not in SUPPORTED_THREAD_TYPES:
            continue
        operation = operation_value
        thread_type = thread_type_value
        if operation == "create" and denies_new_thread:
            continue
        perspective_value = str(raw.get("perspective") or "").strip().lower()
        if perspective_value and perspective_value not in SUPPORTED_PERSPECTIVES:
            continue
        perspective = perspective_value or "shared"
        default_layer = "promise" if thread_type == "promise" else "reality"
        world_layer_value = str(raw.get("world_layer") or "").strip().lower()
        if world_layer_value and world_layer_value not in SUPPORTED_WORLD_LAYERS:
            continue
        world_layer = world_layer_value or default_layer
        target_id = normalize_optional_uuid(raw.get("target_id"))
        if operation != "create" and target_id is None:
            continue

        title = clean_text(raw.get("title"), 160)
        summary = clean_text(raw.get("summary"), 1200)
        if operation == "create" and (not title or not summary):
            continue

        follow_up_at = parse_candidate_datetime(raw.get("follow_up_at"), reference_now)
        normalized.append(
            {
                "operation": operation,
                "thread_type": thread_type,
                "perspective": perspective,
                "world_layer": world_layer,
                "title": title,
                "summary": summary,
                "target_id": target_id,
                "follow_up_at": follow_up_at.isoformat() if follow_up_at else None,
                "proactive_allowed": as_bool(raw.get("proactive_allowed")) and authorized,
                "source_message_id": clean_text(raw.get("source_message_id"), 128),
                "source_turn_id": clean_text(raw.get("source_turn_id"), 128),
            }
        )
    return normalized


def deterministic_thread_hints(message: str, now: datetime | None = None) -> list[dict[str, Any]]:
    """在模型不可用时识别少量高置信度开放事项或直接关系纠偏。

    本地规则刻意保持窄范围：假设句、普通“明天见”和没有行动语义的未来表达
    不会创建线程。该函数只提供候选，不写数据库、不安排主动消息。
    """

    text_value = " ".join(str(message or "").split()).strip()
    if not text_value or text_value.startswith(HYPOTHETICAL_PREFIXES):
        return []
    if text_value.rstrip("。！？!? ") in TRIVIAL_FUTURE_PHRASES:
        return []
    if any(re.search(pattern, text_value) for pattern in NEGATED_OPEN_THREAD_PATTERNS):
        return []

    reference_now = normalize_datetime(now or datetime.now(UTC))
    if any(re.search(pattern, text_value) for pattern in CONFLICT_PATTERNS):
        return [
            {
                "operation": "create",
                "thread_type": "conflict",
                "perspective": "shared",
                "world_layer": "shared_history",
                "title": "需要记住的互动纠偏",
                "summary": text_value[:1200],
                "target_id": None,
                "follow_up_at": None,
                "proactive_allowed": False,
                "source_message_id": None,
                "source_turn_id": None,
            }
        ]

    authorized = has_explicit_follow_up_authorization(text_value)
    has_open_signal = authorized or any(re.search(pattern, text_value) for pattern in OPEN_THREAD_PATTERNS)
    if not has_open_signal:
        return []

    # follow_up_at 也可只用于“下次聊天时已经到期”的上下文排序；是否允许后台主动
    # 发送由 proactive_allowed 独立控制，不能把两者混为同一权限。
    follow_up_at = infer_relative_follow_up_at(text_value, reference_now)
    return [
        {
            "operation": "create",
            "thread_type": "follow_up" if authorized else "open_item",
            "perspective": "user",
            "world_layer": "reality",
            "title": compact_title(text_value),
            "summary": text_value[:1200],
            "target_id": None,
            "follow_up_at": follow_up_at.isoformat() if follow_up_at else None,
            "proactive_allowed": authorized,
            "source_message_id": None,
            "source_turn_id": None,
        }
    ]


def build_source_key(
    user_id: str,
    source_message_id: str,
    candidate: dict[str, Any],
) -> str:
    """生成跨进程稳定的线程来源键，用数据库唯一约束实现抽取幂等。

    用户 ID、原消息 ID、抽取器版本和规范化业务字段共同参与 SHA-256。网络重试
    或后台任务重跑会得到相同键，而不同用户和不同原消息不会互相冲突。
    """

    normalized_user_id = str(UUID(str(user_id)))
    normalized_message_id = clean_text(source_message_id, 128)
    if not normalized_message_id:
        raise ValueError("source_message_id 不能为空")
    canonical_candidate = {
        key: candidate.get(key)
        for key in (
            "operation",
            "thread_type",
            "perspective",
            "world_layer",
            "title",
            "summary",
            "target_id",
            "follow_up_at",
            "proactive_allowed",
        )
    }
    payload = json.dumps(
        {
            "version": EXTRACTOR_VERSION,
            "user_id": normalized_user_id,
            "source_message_id": normalized_message_id,
            "candidate": canonical_candidate,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"rt:{EXTRACTOR_VERSION}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def parse_candidate_container(raw_value: Any) -> list[Any]:
    """把几种常见模型 JSON 外壳统一转换为列表。"""

    value = raw_value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, dict) and "relationship_threads" in value:
        value = value.get("relationship_threads")
    if isinstance(value, dict):
        return [value]
    return value if isinstance(value, list) else []


def has_explicit_follow_up_authorization(message: str) -> bool:
    """判断用户是否明确授权 Aura 在未来询问或提醒。"""

    text_value = str(message or "")
    if any(re.search(pattern, text_value) for pattern in FOLLOW_UP_DENIAL_PATTERNS):
        return False
    return any(re.search(pattern, text_value) for pattern in FOLLOW_UP_AUTHORIZATION_PATTERNS)


def parse_candidate_datetime(value: Any, reference_now: datetime) -> datetime | None:
    """解析模型给出的 ISO 时间并统一为 UTC；过去时间视为无效。"""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    normalized = normalize_datetime(parsed)
    return normalized if normalized > reference_now else None


def normalize_datetime(value: datetime) -> datetime:
    """把无时区时间按上海时间解释，再转换成 UTC。"""

    if value.tzinfo is None:
        value = value.replace(tzinfo=AURA_TIMEZONE)
    return value.astimezone(UTC)


def infer_relative_follow_up_at(message: str, reference_now: datetime) -> datetime | None:
    """为明确授权但未给具体时刻的“明天/后天”生成温和的本地上午时间。"""

    local_now = reference_now.astimezone(AURA_TIMEZONE)
    day_offset = 2 if "后天" in message else 1 if "明天" in message else 0
    if day_offset == 0:
        return None
    target_date = local_now.date() + timedelta(days=day_offset)
    return datetime.combine(target_date, time(hour=10), tzinfo=AURA_TIMEZONE).astimezone(UTC)


def compact_title(message: str) -> str:
    """把原句压缩为不丢失主题的短标题。"""

    text_value = re.sub(r"(?:记得|别忘了)(?:到时候)?(?:问|提醒)我", "", message).strip(" ，。！？!?：:")
    return (text_value or "需要后续接上的事情")[:80]


def normalize_optional_uuid(value: Any) -> str | None:
    """规范可选 UUID；无效值返回 ``None``。"""

    if value is None or value == "":
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return None


def clean_text(value: Any, max_length: int) -> str | None:
    """去除首尾空白并限制文本长度；空值返回 ``None``。"""

    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip()
    return normalized[:max_length] if normalized else None


def as_bool(value: Any) -> bool:
    """只接受明确的布尔真值，避免字符串 ``"false"`` 被 Python 当成真。"""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return value == 1
