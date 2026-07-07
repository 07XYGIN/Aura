from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


@dataclass(frozen=True)
class LLMProviderSpec:
    name: str
    api_key_env: str
    base_url_env: str
    model_env: str
    memory_model_env: str
    default_base_url: str | None
    default_model: str
    default_memory_model: str | None = None
    supports_thinking: bool = False
    supports_reasoning_effort: bool = False
    supports_json_mode: bool = True


@dataclass(frozen=True)
class ActiveLLMConfig:
    provider: LLMProviderSpec
    api_key: str
    base_url: str | None
    model: str
    memory_model: str


COMMON_LLM_PROVIDERS: dict[str, LLMProviderSpec] = {
    "longcat": LLMProviderSpec(
        name="longcat",
        api_key_env="LONGCAT_API_KEY",
        base_url_env="LONGCAT_BASE_URL",
        model_env="LONGCAT_MODEL",
        memory_model_env="LONGCAT_MEMORY_MODEL",
        default_base_url="https://api.longcat.chat/openai",
        default_model="LongCat-2.0",
        supports_thinking=True,
        supports_json_mode=False,
    ),
    "deepseek": LLMProviderSpec(
        name="deepseek",
        api_key_env="DEEPSEEK_API_KEY",
        base_url_env="DEEPSEEK_BASE_URL",
        model_env="DEEPSEEK_MODEL",
        memory_model_env="DEEPSEEK_MEMORY_MODEL",
        default_base_url="https://api.deepseek.com",
        default_model="deepseek-v4-pro",
        default_memory_model="deepseek-v4-flash",
        supports_thinking=True,
        supports_reasoning_effort=True,
        supports_json_mode=True,
    ),
    "openai": LLMProviderSpec(
        name="openai",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        model_env="OPENAI_MODEL",
        memory_model_env="OPENAI_MEMORY_MODEL",
        default_base_url=None,
        default_model="gpt-4o-mini",
        supports_json_mode=True,
    ),
    "dashscope": LLMProviderSpec(
        name="dashscope",
        api_key_env="DASHSCOPE_API_KEY",
        base_url_env="DASHSCOPE_BASE_URL",
        model_env="DASHSCOPE_MODEL",
        memory_model_env="DASHSCOPE_MEMORY_MODEL",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        supports_json_mode=True,
    ),
}


def float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


def csv_env(name: str, default: str = "") -> list[str]:
    value = os.getenv(name, default)
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def resolve_provider_spec(name: str) -> LLMProviderSpec:
    normalized = (name or "").strip().lower()
    if normalized not in COMMON_LLM_PROVIDERS:
        supported = ", ".join(sorted(COMMON_LLM_PROVIDERS))
        raise RuntimeError(f"Unsupported AURA_LLM_PROVIDER={name!r}. Supported providers: {supported}")
    return COMMON_LLM_PROVIDERS[normalized]


def resolve_active_llm_config() -> ActiveLLMConfig:
    primary_name = os.getenv("AURA_LLM_PROVIDER", "longcat").strip().lower()
    provider_names = [primary_name, *csv_env("AURA_LLM_FALLBACK_PROVIDERS")]
    seen: set[str] = set()
    ordered_provider_names = []
    for provider_name in provider_names:
        if provider_name and provider_name not in seen:
            ordered_provider_names.append(provider_name)
            seen.add(provider_name)

    resolved_specs = [resolve_provider_spec(provider_name) for provider_name in ordered_provider_names]
    for spec in resolved_specs:
        config = build_active_llm_config(spec)
        if config.api_key:
            return config

    return build_active_llm_config(resolved_specs[0])


def build_active_llm_config(provider: LLMProviderSpec) -> ActiveLLMConfig:
    model = os.getenv(provider.model_env, provider.default_model).strip() or provider.default_model
    memory_model = (
        os.getenv(provider.memory_model_env)
        or provider.default_memory_model
        or model
    )
    return ActiveLLMConfig(
        provider=provider,
        api_key=os.getenv(provider.api_key_env, "").strip(),
        base_url=(os.getenv(provider.base_url_env) or provider.default_base_url),
        model=model,
        memory_model=memory_model.strip() or model,
    )


def env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def use_json_mode(provider: LLMProviderSpec) -> bool:
    mode = os.getenv("AURA_LLM_JSON_MODE", "auto").strip().lower()
    if mode == "auto":
        return provider.supports_json_mode
    return mode in {"1", "true", "yes", "on", "enabled"}


def create_chat_openai(
    *,
    model: str,
    temperature: float | None = None,
    streaming: bool = False,
    json_mode: bool = False,
    thinking_enabled: bool = False,
    reasoning_effort: str | None = None,
) -> ChatOpenAI:
    kwargs: dict[str, object] = {
        "model": model,
        "api_key": ACTIVE_LLM_CONFIG.api_key or f"missing-{ACTIVE_LLM_CONFIG.provider.api_key_env.lower()}",
        "streaming": streaming,
        "stream_usage": False,
    }
    if ACTIVE_LLM_CONFIG.base_url:
        kwargs["base_url"] = ACTIVE_LLM_CONFIG.base_url
    if temperature is not None:
        kwargs["temperature"] = temperature
    if json_mode and use_json_mode(ACTIVE_LLM_CONFIG.provider):
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    if ACTIVE_LLM_CONFIG.provider.supports_thinking:
        kwargs["extra_body"] = {"thinking": {"type": "enabled" if thinking_enabled else "disabled"}}
    if reasoning_effort and ACTIVE_LLM_CONFIG.provider.supports_reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    return ChatOpenAI(**kwargs)


def normalize_reasoning_effort() -> str:
    value = os.getenv("AURA_LLM_REASONING_EFFORT") or os.getenv("DEEPSEEK_REASONING_EFFORT", "high")
    value = value.strip().lower()
    return value if value in {"high", "max"} else "high"


def ensure_llm_api_key() -> None:
    if not ACTIVE_LLM_CONFIG.api_key:
        provider = ACTIVE_LLM_CONFIG.provider
        raise RuntimeError(f"{provider.api_key_env} is required in Server/ai-service/.env")


ACTIVE_LLM_CONFIG = resolve_active_llm_config()
AURA_LLM_TEMPERATURE = float_env("AURA_LLM_TEMPERATURE", 1.0, 0.0, 1.0)
AURA_LLM_REASONING_EFFORT = normalize_reasoning_effort()
STRUCTURED_LLM_THINKING_ENABLED = env_flag(
    "AURA_STRUCTURED_LLM_THINKING_ENABLED",
    ACTIVE_LLM_CONFIG.provider.name == "deepseek",
)

llm = create_chat_openai(
    model=ACTIVE_LLM_CONFIG.model,
    temperature=AURA_LLM_TEMPERATURE,
    streaming=True,
    thinking_enabled=False,
)

structured_reply_llm = create_chat_openai(
    model=ACTIVE_LLM_CONFIG.model,
    streaming=False,
    json_mode=True,
    thinking_enabled=STRUCTURED_LLM_THINKING_ENABLED,
    reasoning_effort=AURA_LLM_REASONING_EFFORT,
)

memory_judge_llm = create_chat_openai(
    model=ACTIVE_LLM_CONFIG.memory_model,
    temperature=0,
    json_mode=True,
    thinking_enabled=False,
)

emotion_judge_llm = create_chat_openai(
    model=ACTIVE_LLM_CONFIG.memory_model,
    temperature=0.1,
    json_mode=True,
    thinking_enabled=False,
)
