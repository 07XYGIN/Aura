"""判断记忆写入、去重和合并内容的 LLM 辅助逻辑。"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from app.core.config import memory_judge_llm
from app.core.continuity.extractor import (
    deterministic_thread_hints,
    normalize_thread_candidates,
)

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
  "signals": string[],
  "relationship_threads": [
    {
      "operation": "create" | "update" | "resolve" | "abandon",
      "thread_type": "open_item" | "follow_up" | "conflict" | "promise" | "project_task",
      "perspective": "user" | "aura" | "shared",
      "world_layer": "reality" | "shared_history" | "imagined" | "wish" | "promise",
      "title": string | null,
      "summary": string | null,
      "target_id": string | null,
      "follow_up_at": string | null,
      "proactive_allowed": boolean
    }
  ]
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
- `content` 必须简洁，保留用户明确说出的场景和具体情境，但不能补写用户没有表达过的心情或原因。
  - 不好：`用户喜欢吃火锅`
  - 好：`提到和朋友聚餐时通常会选火锅，并明确说自己不太能吃辣`
  - 不好：`用户写代码会累`
  - 好：`聊到写代码累了会起来走走，像是他平时调节状态的小习惯`
- `content` 长度控制在 220 个字符以内。
- `confidence` 必须在 0 到 1 之间。

**关系线程规则：**
- 关系线程不是普通向量记忆。只记录确实需要跨对话延续的开放事项、明确后续关心、双方冲突/纠偏、承诺或共同项目任务。
- “明天要面试”“这个 Bug 周末再修”“下次继续聊这个”可以创建线程；普通寒暄、“明天见”、假设句和没有行动含义的闲聊不要创建。
- 用户直接说“你理解错了”“这句话太客服”“别每次都安慰我”时，创建 `conflict`，保持 pending，不能假装已经修复。
- 只有用户原文明确说“记得问我/提醒我/到时候问我/别忘了问我”时，才允许 `proactive_allowed=true`；普通未来事项只能在下次自然聊天时接上。
- 更新、解决或放弃已有线程时，必须从 `active_relationship_threads` 选择完全对应的 `target_id`；拿不准就不要返回候选。
- 现实用 `reality`，已经真实发生的共同互动用 `shared_history`，假想场景用 `imagined`，愿望用 `wish`，明确承诺用 `promise`，禁止混淆。
- 最多返回 3 个真正必要的线程候选；没有则返回空数组。

---

"""

MEMORY_DEDUP_SYSTEM_PROMPT = """
你是 Aura 的记忆去重判断器。比较一条新记忆候选和一条已有长期记忆，只返回一个 JSON 对象。

JSON 结构：
{
  "decision": "duplicate" | "update" | "unrelated",
  "confidence": number,
  "reason": string
}

规则：
- duplicate：描述同一个稳定事实，新内容没有增加重要信息。
- update：新内容明确纠正、替换或实质改变旧事实。
- unrelated：两条记忆彼此独立，即使共享部分词语或主题。
- 保守判断；不能确认应替换旧事实时，选择 unrelated。
"""

MEMORY_MERGE_SYSTEM_PROMPT = """
你是 Aura 的长期记忆整理器。你会收到同一用户几条高度相似、或被明确要求按同一主题归并的长期记忆。
请把它们合并成一条新的长期记忆，必须只返回一个 JSON 对象。

JSON schema:
{
  "title": string,
  "content": string,
  "reason": string
}

合并规则：
- 保留所有有价值的事实、限制、场景和情绪线索，删除真正重复的部分。
- 不要编造原记忆里没有的事实。
- 文字要简洁但有语境，不要写成数据库字段。
- 如果几条记忆有冲突，保留更具体或更新的说法，并在 reason 里说明。
- 如果 payload 里有 topic_query，说明这次是按主题整理，不要求几条记忆完全重复；但仍然只能整合同一主题下互相补充的内容，不要把独立偏好或无关生活事件硬揉在一起。
- content 建议 80-220 字。
"""


@traceable(name="aura_memory_judge")
def judge_memory_candidate(
    message: str,
    emotion_state: dict[str, Any] | None = None,
    *,
    recent_context: str | None = None,
    relationship_context: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """判断用户消息是否应保存为长期或中期记忆。

    Returns:
        包含保存决定、层级、标题、正文、置信度和信号的标准字典。
    """

    text = (message or "").strip()
    if not text:
        return memory_candidate(False, "short", None, None, 0.0, "empty_message", [])

    reference_now = now or datetime.now(UTC)
    payload = {
        "user_message": text,
        "emotion_state": emotion_state or {},
        "recent_context": recent_context or "",
        "active_relationship_threads": relationship_context or "[]",
        "current_time": reference_now.isoformat(),
    }

    try:
        response = memory_judge_llm.invoke(
            [
                SystemMessage(content=MEMORY_JUDGE_SYSTEM_PROMPT.strip()),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ],
        )
        raw_candidate = parse_json_object(message_content_to_text(response.content))
        candidate = normalize_memory_candidate(raw_candidate, text, now=reference_now)
        if not candidate["relationship_threads"]:
            candidate["relationship_threads"] = deterministic_thread_hints(text, now=reference_now)
        return candidate
    except Exception:
        logging.exception("记忆候选判断失败")
        return memory_candidate(
            False,
            "short",
            None,
            None,
            0.0,
            "记忆候选判断失败",
            [],
            deterministic_thread_hints(text, now=reference_now),
        )


@traceable(name="aura_memory_dedup_judge")
def judge_memory_dedup(
    new_content: str,
    existing_content: str,
    existing_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """比较新旧长期记忆，决定重复、更新或互不相关。"""

    payload = {
        "new_memory": (new_content or "").strip(),
        "existing_memory": (existing_content or "").strip(),
        "existing_metadata": existing_metadata or {},
    }

    if not payload["new_memory"] or not payload["existing_memory"]:
        return memory_dedup_decision("unrelated", 0.0, "empty_memory")

    try:
        response = memory_judge_llm.invoke(
            [
                SystemMessage(content=MEMORY_DEDUP_SYSTEM_PROMPT.strip()),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ],
        )
        raw_decision = parse_json_object(message_content_to_text(response.content))
        return normalize_memory_dedup_decision(raw_decision)
    except Exception:
        logging.exception("记忆去重判断失败")
        return memory_dedup_decision("unrelated", 0.0, "记忆去重判断失败")


@traceable(name="aura_memory_merge")
def merge_memory_contents(memories: list[dict[str, Any]], topic_query: str | None = None) -> dict[str, str]:
    """把多条相关记忆整理成一条不添加新事实的长期记忆。"""

    cleaned_memories = [
        {
            "title": clean_string(memory.get("title"), max_length=80, default="未命名记忆"),
            "content": clean_string(memory.get("content"), max_length=300, default=""),
            "create_time": clean_string(memory.get("create_time"), max_length=40, default=None),
        }
        for memory in memories
        if clean_string(memory.get("content"), max_length=300, default="")
    ]
    if not cleaned_memories:
        return memory_merge_result("合并记忆", "", "empty_memory_cluster")

    try:
        response = memory_judge_llm.invoke(
            [
                SystemMessage(content=MEMORY_MERGE_SYSTEM_PROMPT.strip()),
                HumanMessage(
                    content=json.dumps(
                        {
                            "topic_query": clean_string(topic_query, max_length=120, default=None),
                            "memories": cleaned_memories,
                        },
                        ensure_ascii=False,
                    )
                ),
            ],
        )
        raw_result = parse_json_object(message_content_to_text(response.content))
        return normalize_memory_merge_result(raw_result, cleaned_memories)
    except Exception:
        logging.exception("记忆内容合并失败")
        return fallback_memory_merge(cleaned_memories)


def parse_json_object(text: str) -> dict[str, Any]:
    """解析模型返回的 JSON 对象，并兼容代码围栏或前后说明。"""

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        value = json.loads(match.group(0))

    if not isinstance(value, dict):
        raise ValueError("记忆判断结果必须是 JSON 对象")
    return value


def normalize_memory_candidate(
    raw: dict[str, Any],
    source_text: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """校验记忆候选，并在内容为空时使用原消息作为安全回退。"""

    save = as_bool(raw.get("save"))
    memory_scope = clean_string(raw.get("memory_scope"), max_length=16, default="short").lower()
    if memory_scope not in {"long", "mid", "short"}:
        memory_scope = "short"

    if memory_scope == "short":
        save = False

    content = clean_string(raw.get("content"), max_length=220)
    if save and not content:
        content = source_text[:160]

    title = clean_string(raw.get("title"), max_length=30)
    if save and not title:
        title = "对话记忆" if memory_scope == "long" else "近期线索"

    confidence = clamp_float(raw.get("confidence"), default=0.55 if save else 0.0)
    reason = clean_string(raw.get("reason"), max_length=80, default="模型记忆判断")
    signals = clean_signals(raw.get("signals"))

    relationship_threads = normalize_thread_candidates(
        raw.get("relationship_threads"),
        source_text,
        now=now,
    )
    return memory_candidate(
        save,
        memory_scope,
        title,
        content,
        confidence,
        reason,
        signals,
        relationship_threads,
    )


def normalize_memory_dedup_decision(raw: dict[str, Any]) -> dict[str, Any]:
    """把模型去重判断限制为受支持的决策值和置信度。"""

    decision = clean_string(raw.get("decision"), max_length=16, default="unrelated")
    decision = (decision or "unrelated").lower()
    if decision not in {"duplicate", "update", "unrelated"}:
        decision = "unrelated"

    confidence = clamp_float(raw.get("confidence"), default=0.0)
    reason = clean_string(raw.get("reason"), max_length=120, default="模型记忆去重判断")
    return memory_dedup_decision(decision, confidence, reason or "模型记忆去重判断")


def normalize_memory_merge_result(raw: dict[str, Any], memories: list[dict[str, Any]]) -> dict[str, str]:
    """规范化模型合并结果；字段无效时回退到输入记忆。"""

    title = clean_string(raw.get("title"), max_length=80, default=None)
    content = clean_string(raw.get("content"), max_length=260, default=None)
    reason = clean_string(raw.get("reason"), max_length=160, default="模型记忆合并")
    if not title:
        title = clean_string(memories[0].get("title"), max_length=80, default="合并记忆")
    if not content:
        return fallback_memory_merge(memories)
    return memory_merge_result(title or "合并记忆", content, reason or "模型记忆合并")


def fallback_memory_merge(memories: list[dict[str, Any]]) -> dict[str, str]:
    """模型合并失败时拼接输入内容，确保已有事实不会静默丢失。"""

    title = clean_string(memories[0].get("title"), max_length=80, default="合并记忆") or "合并记忆"
    seen: set[str] = set()
    parts: list[str] = []
    for memory in memories:
        content = clean_string(memory.get("content"), max_length=180, default="")
        if not content or content in seen:
            continue
        seen.add(content)
        parts.append(content)
    return memory_merge_result(title, "；".join(parts)[:260], "去重后直接合并")


def message_content_to_text(content: Any) -> str:
    """把模型消息的字符串或内容块统一转换为文本。"""

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
    relationship_threads: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """构造字段稳定的记忆候选字典。"""

    return {
        "save": save,
        "memory_scope": memory_scope,
        "title": title,
        "content": content,
        "confidence": round(confidence, 2),
        "reason": reason,
        "signals": signals,
        "relationship_threads": relationship_threads or [],
    }


def memory_dedup_decision(decision: str, confidence: float, reason: str) -> dict[str, Any]:
    """构造记忆去重决策字典。"""

    return {
        "decision": decision,
        "confidence": round(confidence, 2),
        "reason": reason,
    }


def memory_merge_result(title: str, content: str, reason: str) -> dict[str, str]:
    """构造最终记忆合并结果。"""

    return {
        "title": title,
        "content": content,
        "reason": reason,
    }


def as_bool(value: Any) -> bool:
    """把模型常见布尔表示转换成 Python bool。"""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def clean_string(value: Any, max_length: int, default: str | None = None) -> str | None:
    """清洗并截断可选字符串；空值返回指定默认值。"""

    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text[:max_length]


def clamp_float(value: Any, default: float) -> float:
    """把置信度限制在 0 到 1；无效值返回默认值。"""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number))


def clean_signals(value: Any) -> list[str]:
    """清洗、去重并限制模型返回的记忆信号列表。"""

    if not isinstance(value, list):
        return []

    signals: list[str] = []
    for item in value[:8]:
        signal = clean_string(item, max_length=40)
        if signal:
            signals.append(signal)
    return signals
