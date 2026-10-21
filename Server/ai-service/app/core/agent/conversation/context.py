"""整理聊天历史上下文并校验会话输入。"""

import logging
from typing import Any

SHORT_TERM_MESSAGE_WINDOW = 24


def trim_short_term_messages(messages: list) -> list:
    """保留最近的完整消息块，且不截断 assistant/tool 调用组合。"""

    blocks = build_valid_message_blocks(messages)
    selected: list = []
    selected_count = 0
    for block in reversed(blocks):
        if selected and selected_count + len(block) > SHORT_TERM_MESSAGE_WINDOW:
            break
        selected[0:0] = block
        selected_count += len(block)
    return selected

def build_valid_message_blocks(messages: list) -> list[list]:
    """把历史拆成普通消息或完整工具调用块，并丢弃孤立工具消息。"""

    blocks: list[list] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if is_tool_message(message):
            logging.warning("短期上下文中发现孤立工具消息，已丢弃")
            index += 1
            continue

        if has_tool_calls(message):
            block, next_index = build_complete_tool_block(messages, index)
            if block:
                blocks.append(block)
            else:
                logging.warning("短期上下文中发现不完整工具调用块，已丢弃")
            index = next_index
            continue

        blocks.append([message])
        index += 1
    return blocks

def build_complete_tool_block(messages: list, index: int) -> tuple[list | None, int]:
    """从 AI 工具调用开始收集对应 ToolMessage，并返回块及下一索引。"""

    assistant_message = messages[index]
    expected_ids = set(tool_call_ids(assistant_message))
    block = [assistant_message]
    seen_ids: set[str] = set()
    next_index = index + 1

    while next_index < len(messages) and is_tool_message(messages[next_index]):
        tool_message = messages[next_index]
        block.append(tool_message)
        tool_call_id = tool_message_id(tool_message)
        if tool_call_id:
            seen_ids.add(tool_call_id)
        next_index += 1

    if expected_ids:
        return (block, next_index) if expected_ids.issubset(seen_ids) else (None, next_index)
    return (block, next_index) if len(block) > 1 else (None, next_index)

def is_tool_message(message: Any) -> bool:
    """判断消息是否为 LangChain ToolMessage。"""

    return getattr(message, "type", None) == "tool"

def has_tool_calls(message: Any) -> bool:
    """判断 AI 消息正文或 additional_kwargs 中是否声明了工具调用。"""

    additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
    return bool(getattr(message, "tool_calls", None) or additional_kwargs.get("tool_calls"))

def tool_call_ids(message: Any) -> list[str]:
    """提取 AI 消息内所有非空工具调用 ID。"""

    additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
    raw_tool_calls = getattr(message, "tool_calls", None) or additional_kwargs.get("tool_calls") or []
    ids: list[str] = []
    for tool_call in raw_tool_calls:
        if isinstance(tool_call, dict):
            tool_call_id = tool_call.get("id") or tool_call.get("tool_call_id")
            if isinstance(tool_call_id, str) and tool_call_id:
                ids.append(tool_call_id)
    return ids

def tool_message_id(message: Any) -> str | None:
    """从 ToolMessage 属性或附加元数据中读取关联的工具调用 ID。"""

    tool_call_id = getattr(message, "tool_call_id", None)
    if isinstance(tool_call_id, str) and tool_call_id:
        return tool_call_id
    additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
    tool_call_id = additional_kwargs.get("tool_call_id")
    return tool_call_id if isinstance(tool_call_id, str) and tool_call_id else None

def latest_human_text(messages: list) -> str:
    """返回最近一条用户消息文本；不存在时返回空字符串。"""

    for msg in reversed(messages):
        if getattr(msg, "type", None) == "human":
            content = getattr(msg, "content", "")
            return content if isinstance(content, str) else str(content)
    return ""

def normalize_city_adcode(value: str | None) -> str | None:
    """校验并规范化六位数字城市 adcode。"""

    if not isinstance(value, str):
        return None

    value = value.strip()
    return value if len(value) == 6 and value.isdigit() else None

def format_location_context(city_adcode: str | None) -> str:
    """生成天气工具可用的位置提示，并禁止模型猜测城市。"""

    normalized = normalize_city_adcode(city_adcode)
    if normalized:
        return (
            "【位置上下文】\n"
            f"本轮已获得用户城市 adcode：{normalized}。"
            "只有用户主动询问天气或明确要求根据天气安排时，才可调用 get_weather(city_adcode=该 adcode)。"
        )

    return (
        "【位置上下文】\n"
        "本轮没有可靠城市 adcode。用户询问天气时，不要猜城市或默认北京；先自然确认城市。"
    )
