import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.core.owned_llms import (
    DEEPSEEK,
    DEEPSEEK_FLASH,
    ERGOUZI_GROK_4_5,
    LONGCAT,
    QWEN_3_7_PLUS,
)

load_dotenv()


# Aura uses one stable provider for visible chat and background judgements.
CHAT_MODEL = QWEN_3_7_PLUS
STRUCTURED_REPLY_MODEL = QWEN_3_7_PLUS
MEMORY_JUDGE_MODEL = QWEN_3_7_PLUS
EMOTION_JUDGE_MODEL = QWEN_3_7_PLUS
"""
CHAT_MODEL：主对话模型
structured_reply_llm：把回复整理成 Aura 需要的 JSON 消息数组
memory_judge_llm：判断是否写入记忆、合并记忆
emotion_judge_llm：判断情绪上下文
"""


def float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    """读取浮点环境变量，并将结果限制在给定闭区间内。"""
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def bool_env(name: str, default: bool) -> bool:
    """Read a boolean environment variable with a conservative fallback."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


AURA_LLM_TEMPERATURE = float_env("AURA_LLM_TEMPERATURE", 0.7, 0.0, 2.0)
AURA_LLM_TOP_P = float_env("AURA_LLM_TOP_P", 0.85, 0.0, 1.0)
AURA_LLM_REASONING_EFFORT = os.getenv("AURA_LLM_REASONING_EFFORT", "max")
AURA_LLM_ENABLE_THINKING = bool_env("AURA_LLM_ENABLE_THINKING", False)
AURA_STRUCTURED_REPLY_TEMPERATURE = float_env("AURA_STRUCTURED_REPLY_TEMPERATURE", 0.0, 0.0, 2.0)
AURA_STRUCTURED_REPLY_TOP_P = float_env("AURA_STRUCTURED_REPLY_TOP_P", 0.2, 0.0, 1.0)
AURA_MEMORY_JUDGE_TEMPERATURE = float_env("AURA_MEMORY_JUDGE_TEMPERATURE", 0.0, 0.0, 2.0)
AURA_MEMORY_JUDGE_TOP_P = float_env("AURA_MEMORY_JUDGE_TOP_P", 0.2, 0.0, 1.0)
AURA_EMOTION_JUDGE_TEMPERATURE = float_env("AURA_EMOTION_JUDGE_TEMPERATURE", 0.0, 0.0, 2.0)
AURA_EMOTION_JUDGE_TOP_P = float_env("AURA_EMOTION_JUDGE_TOP_P", 0.2, 0.0, 1.0)


def create_llm(
    model_config: dict,
    *,
    temperature: float | None = None,
    top_p: float | None = None,
    streaming: bool = False,
    json_mode: bool = False,
    thinking_enabled: bool = False,
) -> ChatOpenAI:
    """根据统一模型配置创建 LangChain ``ChatOpenAI`` 客户端。

    Args:
        model_config: 包含模型名、Base URL 和 API Key 环境变量名的配置。
        temperature: 可选采样温度；不传时交由服务商使用默认值。
        top_p: 可选 nucleus sampling 阈值。
        streaming: 是否启用流式输出。
        json_mode: 是否为支持的模型请求 JSON Object 输出模式。
        thinking_enabled: 是否为支持的模型开启思考模式。

    Returns:
        已配置但尚未发起请求的 LangChain 模型客户端。

    Notes:
        不同供应商支持的扩展参数不同，本函数只对已知兼容模型注入对应参数。
    """
    kwargs: dict[str, object] = {
        "model": model_config["model"],
        "api_key": os.getenv(model_config["api_key_env"], ""),
        "base_url": model_config["base_url"],
        "streaming": streaming,
        "stream_usage": False,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if top_p is not None:
        kwargs["top_p"] = top_p
    if json_mode and (
        model_config in (DEEPSEEK, DEEPSEEK_FLASH)
        or model_config.get("supports_json_mode", False)
    ):
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    if model_config in (LONGCAT, DEEPSEEK, DEEPSEEK_FLASH):
        kwargs["extra_body"] = {"thinking": {"type": "enabled" if thinking_enabled else "disabled"}}
    elif model_config.get("provider") == "qwen":
        # Qwen's JSON mode only works when thinking mode is disabled.
        kwargs["extra_body"] = {"enable_thinking": thinking_enabled and not json_mode}
    if model_config in (DEEPSEEK, DEEPSEEK_FLASH) and thinking_enabled:
        kwargs["reasoning_effort"] = AURA_LLM_REASONING_EFFORT
    return ChatOpenAI(**kwargs)


llm = create_llm(
    CHAT_MODEL,
    temperature=AURA_LLM_TEMPERATURE,
    top_p=AURA_LLM_TOP_P,
    streaming=True,
    # Qwen's strict JSON mode conflicts with tool calls. The runtime prompt still
    # requires JSON, while the dedicated formatter repairs malformed replies.
    json_mode=False,
    thinking_enabled=AURA_LLM_ENABLE_THINKING,
)

structured_reply_llm = create_llm(
    STRUCTURED_REPLY_MODEL,
    temperature=AURA_STRUCTURED_REPLY_TEMPERATURE,
    top_p=AURA_STRUCTURED_REPLY_TOP_P,
    json_mode=True,
)

memory_judge_llm = create_llm(
    MEMORY_JUDGE_MODEL,
    temperature=AURA_MEMORY_JUDGE_TEMPERATURE,
    top_p=AURA_MEMORY_JUDGE_TOP_P,
    json_mode=True,
)

emotion_judge_llm = create_llm(
    EMOTION_JUDGE_MODEL,
    temperature=AURA_EMOTION_JUDGE_TEMPERATURE,
    top_p=AURA_EMOTION_JUDGE_TOP_P,
    json_mode=True,
)
