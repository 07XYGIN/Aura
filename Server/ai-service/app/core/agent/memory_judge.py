from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import ensure_deepseek_api_key, memory_judge_llm

MEMORY_JUDGE_SYSTEM_PROMPT = """
You are Aura's memory write judge. Decide whether the latest user message
should be written into the vector memory store. Return only one JSON object.

JSON schema:
{
  "save": boolean,
  "memory_scope": "long" | "mid" | "short",
  "title": string | null,
  "content": string | null,
  "confidence": number,
  "reason": string,
  "signals": string[]
}

Rules:
- long memory: stable user facts, explicit preferences or dislikes, long-term
  habits, important dates, identity/profile details, long-term goals, durable
  relationship milestones. These are suitable for permanent vector retrieval.
- mid memory: recent plans, active projects, temporary stressors, short-lived
  emotional context, or things useful for the next 3-5 days.
- short memory: greetings, jokes, weather/time questions, one-off tool requests,
  generic questions, ordinary small talk, and content with no future recall value.
- Set save=true only for long or mid. Set save=false for short.
- If the user explicitly asks Aura to remember/save something specific, save it
  unless it is unsafe or too vague.
- Do not save private facts that are merely guessed or implied by Aura.
- Preserve the user's language in title/content when possible.
- content must be a concise memory fact, not an analysis. Keep it under 160 chars.
- confidence must be between 0 and 1.
"""


def judge_memory_candidate(message: str, emotion_state: dict[str, Any] | None = None) -> dict[str, Any]:
    text = (message or "").strip()
    if not text:
        return memory_candidate(False, "short", None, None, 0.0, "empty_message", [])

    payload = {
        "user_message": text,
        "emotion_state": emotion_state or {},
    }

    try:
        ensure_deepseek_api_key()
        response = memory_judge_llm.invoke(
            [
                SystemMessage(content=MEMORY_JUDGE_SYSTEM_PROMPT.strip()),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ],
        )
        raw_candidate = parse_json_object(message_content_to_text(response.content))
        return normalize_memory_candidate(raw_candidate, text)
    except Exception:
        logging.exception("Failed to judge memory candidate with DeepSeek")
        return memory_candidate(False, "short", None, None, 0.0, "memory_judge_failed", [])


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        value = json.loads(match.group(0))

    if not isinstance(value, dict):
        raise ValueError("Memory judge response must be a JSON object")
    return value


def normalize_memory_candidate(raw: dict[str, Any], source_text: str) -> dict[str, Any]:
    save = as_bool(raw.get("save"))
    memory_scope = clean_string(raw.get("memory_scope"), max_length=16, default="short").lower()
    if memory_scope not in {"long", "mid", "short"}:
        memory_scope = "short"

    if memory_scope == "short":
        save = False

    content = clean_string(raw.get("content"), max_length=160)
    if save and not content:
        content = source_text[:160]

    title = clean_string(raw.get("title"), max_length=30)
    if save and not title:
        title = "Conversation memory" if memory_scope == "long" else "Recent context"

    confidence = clamp_float(raw.get("confidence"), default=0.55 if save else 0.0)
    reason = clean_string(raw.get("reason"), max_length=80, default="llm_memory_judge")
    signals = clean_signals(raw.get("signals"))

    return memory_candidate(save, memory_scope, title, content, confidence, reason, signals)


def message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return str(content).strip()


def memory_candidate(
    save: bool,
    memory_scope: str,
    title: str | None,
    content: str | None,
    confidence: float,
    reason: str,
    signals: list[str],
) -> dict[str, Any]:
    return {
        "save": save,
        "memory_scope": memory_scope,
        "title": title,
        "content": content,
        "confidence": round(confidence, 2),
        "reason": reason,
        "signals": signals,
    }


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def clean_string(value: Any, max_length: int, default: str | None = None) -> str | None:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text[:max_length]


def clamp_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number))


def clean_signals(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    signals: list[str] = []
    for item in value[:8]:
        signal = clean_string(item, max_length=40)
        if signal:
            signals.append(signal)
    return signals
