"""控制模型可见的短期聊天上下文。"""

SHORT_TERM_MESSAGE_WINDOW = 24


def trim_short_term_messages(messages: list) -> list:
    """只保留最近的固定数量消息。"""

    return list(messages[-SHORT_TERM_MESSAGE_WINDOW:])
