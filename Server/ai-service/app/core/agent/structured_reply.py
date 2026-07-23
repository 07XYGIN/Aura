"""解析并容错修复主模型返回的多气泡 JSON 回复。"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MAX_REPLY_MESSAGES = 4
FALLBACK_REPLY = "我刚才有点卡住了，你再说一遍？"


class StructuredThreadAction(BaseModel):
    """主回复确实接续关系线程后返回的受限状态动作。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    thread_ref: str = Field(alias="threadRef", pattern=r"^T(?:[1-9]|1[0-2])$")
    action: Literal["follow_up"]


class StructuredReply(BaseModel):
    """主模型结构化回复的 Pydantic 校验模型。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    messages: list[str]
    thread_actions: list[StructuredThreadAction] = Field(default_factory=list, alias="threadActions")

    @field_validator("messages", mode="before")
    @classmethod
    def normalize_messages(cls, value: Any) -> list[Any]:
        """允许模型把单个字符串误写成 messages 字段。"""

        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return value
        return []

    @field_validator("messages")
    @classmethod
    def clean_messages(cls, value: list[Any]) -> list[str]:
        """清理空消息并把气泡数量限制为 ``MAX_REPLY_MESSAGES``。"""

        messages = []
        for item in value:
            text = normalize_text(item)
            if text:
                messages.append(text)
            if len(messages) >= MAX_REPLY_MESSAGES:
                break

        if not messages:
            raise ValueError("messages must contain at least one non-empty item")

        return messages

    @field_validator("thread_actions", mode="before")
    @classmethod
    def clean_thread_actions(cls, value: Any) -> list[StructuredThreadAction]:
        """逐条过滤非法引用和动作，不让附加字段破坏正常文本回复。"""

        if not isinstance(value, list):
            return []
        actions: list[StructuredThreadAction] = []
        seen: set[tuple[str, str]] = set()
        for item in value[:12]:
            try:
                action = StructuredThreadAction.model_validate(item)
            except ValidationError:
                continue
            key = (action.thread_ref, action.action)
            if key not in seen:
                actions.append(action)
                seen.add(key)
        return actions


def parse_structured_reply(raw_content: Any) -> list[str]:
    """返回可展示消息列表；JSON 无法解析时把原文本作为单条回复。"""

    parsed = try_parse_structured_reply(raw_content)
    if parsed is not None:
        return parsed

    text = normalize_text(raw_content)
    if not text:
        return [FALLBACK_REPLY]

    return [text]


def try_parse_structured_reply(raw_content: Any) -> list[str] | None:
    """尝试解析严格或容错 JSON；无法识别时返回 ``None``。"""

    parsed = try_parse_structured_reply_payload(raw_content)
    return parsed.messages if parsed is not None else None


def try_parse_structured_reply_payload(raw_content: Any) -> StructuredReply | None:
    """解析完整结构化回复，保留经过白名单校验的关系线程动作。"""

    text = normalize_text(raw_content)
    if not text:
        return None

    for candidate in json_candidates(text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            tolerant_messages = parse_tolerant_messages(candidate)
            if tolerant_messages:
                return StructuredReply(messages=tolerant_messages)
            continue

        try:
            if isinstance(data, list):
                return StructuredReply(messages=data)
            if isinstance(data, dict):
                if "messages" not in data:
                    fallback_value = data.get("message") or data.get("content") or data.get("reply")
                    data = {**data, "messages": [fallback_value] if fallback_value else []}
                return StructuredReply.model_validate(data)
        except ValidationError:
            continue

    return None


def parse_tolerant_messages(text: str) -> list[str]:
    """从转义不完整但仍含 messages 数组的文本中恢复消息。"""

    if '"messages"' not in text and "'messages'" not in text:
        return []

    match = re.search(r"""["']messages["']\s*:\s*\[\s*["']""", text)
    if not match:
        return []

    start = match.end()
    end = text.rfind('"]')
    if end < start:
        end = text.rfind("']")
    if end < start:
        return []

    body = text[start:end]
    if not body.strip():
        return []

    parts = split_tolerant_string_array(body)
    messages = [clean_tolerant_message(part) for part in parts]
    messages = [message for message in messages if message]
    return messages[:MAX_REPLY_MESSAGES]


def split_tolerant_string_array(body: str) -> list[str]:
    """在不破坏转义字符的前提下拆分近似 JSON 字符串数组。"""

    parts: list[str] = []
    current: list[str] = []
    index = 0
    in_string = True
    escaped = False

    while index < len(body):
        char = body[index]
        next_two = body[index : index + 3]

        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            current.append(char)
            escaped = True
        elif in_string and next_two == '","':
            parts.append("".join(current))
            current = []
            index += 2
        else:
            current.append(char)

        index += 1

    parts.append("".join(current))
    return parts


def clean_tolerant_message(value: str) -> str:
    """恢复常见 JSON 转义并清理单条容错消息。"""

    value = value.strip()
    if not value:
        return ""

    try:
        value = json.loads(f'"{value}"')
    except json.JSONDecodeError:
        value = value.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")

    return normalize_text(value)


def normalize_text(value: Any) -> str:
    """把字符串、内容块列表或标量统一转换成去空白文本。"""

    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "".join(normalize_text(item) for item in value).strip()
    return str(value).strip()


def json_candidates(text: str) -> list[str]:
    """返回完整文本及其中第一个 JSON 对象作为候选。"""

    stripped = strip_markdown_fence(text)
    candidates = [stripped]

    extracted = extract_first_json_object(stripped)
    if extracted and extracted not in candidates:
        candidates.append(extracted)

    return candidates


def strip_markdown_fence(text: str) -> str:
    """移除包裹整个响应的 Markdown JSON 代码围栏。"""

    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def extract_first_json_object(text: str) -> str | None:
    """按括号深度提取第一个完整 JSON 对象，并正确跳过字符串内容。"""

    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None
