from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import ensure_deepseek_api_key, memory_judge_llm

MEMORY_JUDGE_SYSTEM_PROMPT = """
---

**你是一名 Aura 的记忆写入裁判。请判断最新一条用户消息是否应被写入向量记忆存储。仅返回一个 JSON 对象。**

**JSON 结构：**
```json
{
  "save": boolean,
  "memory_scope": "long" | "mid" | "short",
  "title": string | null,
  "content": string | null,
  "confidence": number,
  "reason": string,
  "signals": string[]
}
```

**规则：**
- **长期记忆**：稳定的用户事实、明确的偏好或厌恶、长期习惯、重要日期、身份/个人资料细节、长期目标、持久的关系里程碑。此类内容适合永久向量检索。
- **中期记忆**：近期计划、活跃中的项目、临时压力源、短期内的情绪背景，或未来 3-5 天内有用的内容。
- **短期记忆**：问候、玩笑、天气/时间询问、一次性工具请求、普通问题、寻常闲聊，以及没有未来回忆价值的内容。
- 仅对 **长期** 或 **中期** 记忆设置 `save=true`。对于 **短期** 记忆，设置 `save=false`。
- 如果用户明确要求 Aura 记住/保存某件具体事情，则予以保存，除非它不安全或过于模糊。
- 不要保存仅由 Aura 猜测或暗示得到的私人事实。
- 尽可能在标题/内容中保留用户的原始语言。
- `content` 必须是简洁的记忆事实，而非分析性内容。长度控制在 160 个字符以内。
- `confidence` 必须在 0 到 1 之间。

---

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
