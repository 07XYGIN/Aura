"""校验记忆 judge 提出的时间胶囊和秘密保险箱候选。

模型只能帮助理解自然语言，不能替用户授予未来主动投递权限。这里会重新检查用户
原文中的明确动作、否定表达、证据和条件字段；普通的“明天要发布”永远不会因为
模型返回 ``authorized=true`` 就升级成条件消息。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

SUPPORTED_MESSAGE_TYPES = {"time_capsule", "secret_vault"}
SUPPORTED_CONDITION_TYPES = {"time", "keyword", "project_status", "github_event", "passphrase"}
EXPLICIT_ACTION_PATTERN = re.compile(
    r"(?:"
    r"(?:等|到).{0,40}(?:时|后|以后).{0,30}(?:发给我|告诉我|拿出来|打开|提醒我|给我看)"
    r"|(?:记得|别忘了).{0,30}(?:发给我|告诉我|拿出来|打开|提醒我)"
    r"|(?:时间胶囊|秘密保险箱|保险箱|封存).{0,40}(?:打开|解锁|口令|密码|发给我|告诉我|存下|保存)"
    r"|(?:等到|留到).{1,40}(?:把|将).{1,80}(?:发给我|告诉我|拿出来|打开|解锁)"
    r"|(?:把|将).{1,80}(?:等到|留到|封存到).{1,40}(?:发给我|告诉我|拿出来|打开|解锁)"
    r")"
)
DENIAL_PATTERN = re.compile(
    r"(?:不用|不要|别(?!忘了)|取消|算了).{0,16}(?:提醒|保存|封存|时间胶囊|保险箱|发给我|告诉我|拿出来)"
)


def normalize_conditional_message_candidates(
    value: Any,
    source_text: str,
    *,
    recent_context: str = "",
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """把模型候选收紧成可交给 Pydantic 和服务层的创建参数。

    Returns:
        最多两条证据充分的候选。返回值仍不含用户 ID 或幂等键，这些字段只能由
        聊天链路使用 JWT/客户端消息 ID 补入。
    """

    source = str(source_text or "").strip()
    if not isinstance(value, list) or not has_explicit_conditional_authorization(source):
        return []
    evidence_space = f"{source}\n{recent_context or ''}"
    reference_now = normalize_utc(now or datetime.now(UTC))
    candidates: list[dict[str, Any]] = []
    for raw in value[:4]:
        if not isinstance(raw, dict) or not bool(raw.get("authorized")):
            continue
        message_type = clean_text(raw.get("message_type") or raw.get("messageType"), 24)
        condition_type = clean_text(raw.get("condition_type") or raw.get("conditionType"), 24)
        content = clean_text(raw.get("content"), 8000)
        evidence = clean_text(raw.get("evidence"), 500)
        if message_type not in SUPPORTED_MESSAGE_TYPES or condition_type not in SUPPORTED_CONDITION_TYPES:
            continue
        if not content or content not in evidence_space:
            continue
        if not evidence or evidence not in evidence_space:
            continue

        condition = normalize_candidate_condition(condition_type, raw.get("condition"), source)
        if condition is None:
            continue
        deliver_at = parse_iso_datetime(raw.get("deliver_at") or raw.get("deliverAt"))
        if condition_type == "time":
            if deliver_at is None or deliver_at <= reference_now:
                continue
        elif deliver_at is not None:
            continue

        passphrase = clean_text(raw.get("passphrase"), 128)
        if condition_type == "passphrase":
            if not passphrase or passphrase not in source:
                continue
        elif passphrase:
            continue

        expires_at = parse_iso_datetime(raw.get("expires_at") or raw.get("expiresAt"))
        if expires_at is not None and expires_at <= reference_now:
            continue
        if deliver_at is not None and expires_at is not None and expires_at <= deliver_at:
            continue
        candidates.append(
            {
                "messageType": message_type,
                "conditionType": condition_type,
                "title": clean_text(raw.get("title"), 160) or default_title(message_type),
                "content": content,
                "deliverAt": deliver_at.isoformat() if deliver_at else None,
                "condition": condition,
                "passphrase": passphrase,
                "expiresAt": expires_at.isoformat() if expires_at else None,
                "metadata": {
                    "capture_source": "memory_judge",
                    "extractor_version": "conditional-message-v1",
                },
            }
        )
        if len(candidates) >= 2:
            break
    return candidates


def has_explicit_conditional_authorization(source_text: str) -> bool:
    """判断用户原文是否同时包含未来条件和明确交付动作。"""

    source = str(source_text or "").strip()
    if not source or DENIAL_PATTERN.search(source):
        return False
    return bool(EXPLICIT_ACTION_PATTERN.search(source))


def normalize_candidate_condition(
    condition_type: str,
    value: Any,
    source_text: str,
) -> dict[str, str] | None:
    """校验条件字段确实有原文依据，并剥离模型添加的多余 metadata。"""

    condition = value if isinstance(value, dict) else {}
    if condition_type in {"time", "passphrase"}:
        return {}
    if condition_type == "keyword":
        keyword = clean_text(condition.get("keyword"), 160)
        match_mode = clean_text(condition.get("matchMode") or "contains", 16)
        if not keyword or keyword not in source_text or match_mode not in {"contains", "exact"}:
            return None
        return {"keyword": keyword, "matchMode": match_mode}
    if condition_type == "project_status":
        project_key = clean_text(condition.get("projectKey"), 160)
        expected_status = clean_text(condition.get("expectedStatus"), 80)
        if not project_key or not expected_status:
            return None
        if project_key not in source_text and expected_status not in source_text:
            return None
        return {"projectKey": project_key, "expectedStatus": expected_status}
    if condition_type == "github_event":
        repository = clean_text(condition.get("repository"), 240)
        event = clean_text(condition.get("event"), 80)
        if not repository or not event or repository not in source_text:
            return None
        normalized = {"repository": repository, "event": event}
        for key in ("action", "conclusion", "ref"):
            optional_value = clean_text(condition.get(key), 240)
            if optional_value:
                normalized[key] = optional_value
        return normalized
    return None


def parse_iso_datetime(value: Any) -> datetime | None:
    """解析模型给出的 ISO 时间并统一到 UTC；其他格式直接拒绝。"""

    if isinstance(value, datetime):
        return normalize_utc(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return normalize_utc(parsed)


def normalize_utc(value: datetime) -> datetime:
    """把无时区时间保守地视作 UTC，并统一返回 UTC。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def clean_text(value: Any, max_length: int) -> str | None:
    """清理模型文本字段并限制长度。"""

    if value is None:
        return None
    normalized = str(value).strip()
    return normalized[:max_length] if normalized else None


def default_title(message_type: str) -> str:
    """候选没有标题时提供稳定、不过度解释内容的默认值。"""

    return "留给未来的一句话" if message_type == "time_capsule" else "密封的一句话"
