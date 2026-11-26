"""Aura 唯一的 LLM 配置源：可用模型注册表 + 客户端工厂。

设计约定：
- ``LLM_DICT`` 是全部可切换 LLM 的唯一登记处，模型名、base_url 与 API Key
  环境变量名都写在这里，业务代码只按 ``llm_name`` 取配置。
- 代码里永远不出现 API Key 字面量，只记录"去哪里读"（``api_key_env``）。
- 能力位（JSON 模式、thinking）属于模型配置，不属于调用方，避免调用方散落
  ``if provider == "qwen"`` 这类分支。
"""

from __future__ import annotations

import logging
import os
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


class LLMConfig(TypedDict):
    """一个已注册 LLM 的静态配置。

    Attributes:
        llm_name: 注册表内唯一名称，业务代码用它取配置。
        model: 传给 OpenAI 兼容接口的模型 ID。
        base_url: OpenAI 兼容接口根地址。
        api_key_env: 保存 API Key 的环境变量名，不保存 Key 本身。
        provider: 供应商标识，用于日志与排查，不参与能力判断。
        supports_json_mode: 是否支持 ``response_format=json_object``。
        supports_thinking: 是否支持 ``enable_thinking`` 扩展开关。
    """

    llm_name: str
    model: str
    base_url: str
    api_key_env: str
    provider: str
    supports_json_mode: bool
    supports_thinking: bool


FALLBACK_LLM_NAME = "qwen"


def _env_text(name: str, default: str) -> str:
    """读取文本环境变量，空字符串视为未配置。

    ``.env`` 里常见的 ``QWEN_MODEL=`` 写法会让 ``os.getenv`` 返回空串而不是
    默认值，这里显式兜住，避免拼出一个没有模型名的空配置。

    Args:
        name: 环境变量名。
        default: 变量缺失或为空时使用的值。

    Returns:
        去除首尾空白后的非空字符串。
    """

    return (os.getenv(name) or "").strip() or default


# 默认模型放在第一位；新增供应商只需追加一项，env 可覆盖模型名与地址。
LLM_DICT: list[LLMConfig] = [
    {
        "llm_name": "qwen",
        "model": _env_text("QWEN_MODEL", "qwen3.8-max"),
        "base_url": _env_text("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "api_key_env": "DASHSCOPE_API_KEY",
        "provider": "qwen",
        "supports_json_mode": True,
        "supports_thinking": True,
    },
    {
        "llm_name": "deepseek",
        "model": _env_text("DEEPSEEK_MODEL", "deepseek-chat"),
        "base_url": _env_text("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "api_key_env": "DEEPSEEK_API_KEY",
        "provider": "deepseek",
        "supports_json_mode": True,
        "supports_thinking": False,
    },
    {
        "llm_name": "zhipu",
        "model": _env_text("ZAI_MODEL", "glm-4.6"),
        "base_url": _env_text("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        "api_key_env": "ZAI_API_KEY",
        "provider": "zhipu",
        "supports_json_mode": True,
        "supports_thinking": False,
    },
]



def _index_registry(registry: list[LLMConfig]) -> dict[str, LLMConfig]:
    """把注册表按名称建索引，并在出现重名时立即失败。

    Args:
        registry: 待建索引的 LLM 配置列表。

    Returns:
        以 ``llm_name`` 为键的有序索引，保持注册表原始顺序。

    Raises:
        ValueError: 注册表中存在重复的 ``llm_name``。
    """

    index: dict[str, LLMConfig] = {}
    duplicates: set[str] = set()
    for config in registry:
        name = config["llm_name"]
        if name in index:
            duplicates.add(name)
        index[name] = config
    if duplicates:
        raise ValueError(f"LLM_DICT 中存在重复的 llm_name: {', '.join(sorted(duplicates))}")
    return index


LLM_BY_NAME: dict[str, LLMConfig] = _index_registry(LLM_DICT)


def get_llm(name: str) -> LLMConfig:
    """按名称取出注册表中的 LLM 配置。

    Args:
        name: 注册时的 ``llm_name``，例如 ``qwen``。

    Returns:
        注册表中该名称对应的配置对象本身（同一引用，不做拷贝）。

    Raises:
        KeyError: 名称未注册。
    """

    config = LLM_BY_NAME.get(name)
    if config is None:
        raise KeyError(f"未注册的 LLM {name!r}，可选: {', '.join(LLM_BY_NAME)}")
    return config


def list_llm_names() -> tuple[str, ...]:
    """返回全部已注册 LLM 的名称，顺序与 ``LLM_DICT`` 一致。"""

    return tuple(LLM_BY_NAME)


def resolve_api_key(config: LLMConfig) -> str:
    """读取某个 LLM 当前生效的 API Key。

    Args:
        config: 已注册的 LLM 配置。

    Returns:
        环境变量中的 Key；未配置时返回空字符串，由调用方决定如何降级。
    """

    return os.getenv(config["api_key_env"], "").strip()


def llm_availability() -> dict[str, bool]:
    """统计每个已注册 LLM 在当前环境是否可用（有无 API Key）。

    Returns:
        名称到可用状态的映射，顺序与 ``LLM_DICT`` 一致，可直接用于启动自检
        或管理端展示。
    """

    return {name: bool(resolve_api_key(config)) for name, config in LLM_BY_NAME.items()}


def resolve_default_llm_name() -> str:
    """解析默认 LLM 名称。

    未配置 ``AURA_LLM_NAME`` 时使用 ``FALLBACK_LLM_NAME``；配置了未注册的名称
    时记录告警并回退，避免一处拼写错误导致整个服务起不来。

    Returns:
        一定存在于注册表中的 LLM 名称。
    """

    name = (os.getenv("AURA_LLM_NAME") or FALLBACK_LLM_NAME).strip() or FALLBACK_LLM_NAME
    if name not in LLM_BY_NAME:
        logging.warning(
            "AURA_LLM_NAME 未注册，回退到 %s name=%s 可选=%s",
            FALLBACK_LLM_NAME,
            name,
            ", ".join(LLM_BY_NAME),
        )
        return FALLBACK_LLM_NAME
    return name


DEFAULT_LLM_NAME = resolve_default_llm_name()


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
AURA_LLM_ENABLE_THINKING = bool_env("AURA_LLM_ENABLE_THINKING", False)
AURA_STRUCTURED_REPLY_TEMPERATURE = float_env("AURA_STRUCTURED_REPLY_TEMPERATURE", 0.0, 0.0, 2.0)
AURA_STRUCTURED_REPLY_TOP_P = float_env("AURA_STRUCTURED_REPLY_TOP_P", 0.2, 0.0, 1.0)
AURA_MEMORY_JUDGE_TEMPERATURE = float_env("AURA_MEMORY_JUDGE_TEMPERATURE", 0.0, 0.0, 2.0)
AURA_MEMORY_JUDGE_TOP_P = float_env("AURA_MEMORY_JUDGE_TOP_P", 0.2, 0.0, 1.0)
AURA_EMOTION_JUDGE_TEMPERATURE = float_env("AURA_EMOTION_JUDGE_TEMPERATURE", 0.0, 0.0, 2.0)
AURA_EMOTION_JUDGE_TOP_P = float_env("AURA_EMOTION_JUDGE_TOP_P", 0.2, 0.0, 1.0)


def create_llm(
    model_config: LLMConfig,
    *,
    temperature: float | None = None,
    top_p: float | None = None,
    streaming: bool = False,
    json_mode: bool = False,
    thinking_enabled: bool = False,
) -> ChatOpenAI:
    """根据统一模型配置创建 LangChain ``ChatOpenAI`` 客户端。

    Args:
        model_config: 注册表中的一项配置，包含模型名、Base URL 与 Key 环境变量名。
        temperature: 可选采样温度；不传时交由服务商使用默认值。
        top_p: 可选 nucleus sampling 阈值。
        streaming: 是否启用流式输出。
        json_mode: 是否为支持的模型请求 JSON Object 输出模式；不支持该能力的
            模型会静默跳过，不会带上无效参数。
        thinking_enabled: 是否为支持的模型开启思考模式；JSON 模式下强制关闭，
            因为 Qwen 的 JSON 模式与 thinking 互斥。

    Returns:
        已配置但尚未发起请求的 LangChain 模型客户端。

    Raises:
        KeyError: ``model_config`` 缺少 ``create_llm`` 需要的字段。
    """

    kwargs: dict[str, Any] = {
        "model": model_config["model"],
        "api_key": resolve_api_key(model_config),
        "base_url": model_config["base_url"],
        "streaming": streaming,
        "stream_usage": False,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if top_p is not None:
        kwargs["top_p"] = top_p
    if json_mode and model_config["supports_json_mode"]:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    if model_config["supports_thinking"]:
        # 能力位由注册表声明，调用方不再按 vendor 名做分支。
        kwargs["extra_body"] = {"enable_thinking": thinking_enabled and not json_mode}
    return ChatOpenAI(**kwargs)


# 四个使用场景共用同一默认模型，采样参数各自独立；换模型只改 AURA_LLM_NAME。
CHAT_MODEL = get_llm(DEFAULT_LLM_NAME)
STRUCTURED_REPLY_MODEL = get_llm(DEFAULT_LLM_NAME)
MEMORY_JUDGE_MODEL = get_llm(DEFAULT_LLM_NAME)
EMOTION_JUDGE_MODEL = get_llm(DEFAULT_LLM_NAME)

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
