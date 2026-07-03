from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator

MAX_REPLY_MESSAGES = 4
FALLBACK_REPLY = "我刚才有点卡住了，你再说一遍？"


class StructuredReply(BaseModel):
    messages: list[str]

    @field_validator("messages", mode="before")
    @classmethod
    def normalize_messages(cls, value: Any) -> list[Any]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return value
        return []

    @field_validator("messages")
    @classmethod
    def clean_messages(cls, value: list[Any]) -> list[str]:
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


def parse_structured_reply(raw_content: Any) -> list[str]:
    text = normalize_text(raw_content)
    if not text:
        return [FALLBACK_REPLY]

    for candidate in json_candidates(text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            tolerant_messages = parse_tolerant_messages(candidate)
            if tolerant_messages:
                return tolerant_messages
            continue

        try:
            if isinstance(data, list):
                return StructuredReply(messages=data).messages
            if isinstance(data, dict):
                if "messages" not in data:
                    fallback_value = data.get("message") or data.get("content") or data.get("reply")
                    data = {"messages": [fallback_value] if fallback_value else []}
                return StructuredReply.model_validate(data).messages
        except ValidationError:
            continue

    return [text]


def parse_tolerant_messages(text: str) -> list[str]:
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
    value = value.strip()
    if not value:
        return ""

    try:
        value = json.loads(f'"{value}"')
    except json.JSONDecodeError:
        value = value.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")

    return normalize_text(value)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "".join(normalize_text(item) for item in value).strip()
    return str(value).strip()


def json_candidates(text: str) -> list[str]:
    stripped = strip_markdown_fence(text)
    candidates = [stripped]

    extracted = extract_first_json_object(stripped)
    if extracted and extracted not in candidates:
        candidates.append(extracted)

    return candidates


def strip_markdown_fence(text: str) -> str:
    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def extract_first_json_object(text: str) -> str | None:
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
