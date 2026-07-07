from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.core.owned_llms import OWNED_LLMS

load_dotenv()


def float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


def bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


ACTIVE_PROVIDER = os.getenv("AURA_LLM_PROVIDER", "longcat").strip().lower()
ACTIVE_LLM = OWNED_LLMS[ACTIVE_PROVIDER]
AURA_LLM_TEMPERATURE = float_env("AURA_LLM_TEMPERATURE", 1.0, 0.0, 1.0)
AURA_LLM_REASONING_EFFORT = os.getenv("AURA_LLM_REASONING_EFFORT") or os.getenv("DEEPSEEK_REASONING_EFFORT", "high")
if AURA_LLM_REASONING_EFFORT not in {"high", "max"}:
    AURA_LLM_REASONING_EFFORT = "high"


def create_llm(
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
        "api_key": ACTIVE_LLM["api_key"],
        "base_url": ACTIVE_LLM["base_url"],
        "streaming": streaming,
        "stream_usage": False,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if json_mode and ACTIVE_LLM["json_mode"]:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    if ACTIVE_LLM["thinking"]:
        kwargs["extra_body"] = {"thinking": {"type": "enabled" if thinking_enabled else "disabled"}}
    if ACTIVE_PROVIDER == "deepseek" and reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    return ChatOpenAI(**kwargs)


# Main chat model: Aura's final user-facing reply.
llm = create_llm(
    model=ACTIVE_LLM["chat_model"],
    temperature=AURA_LLM_TEMPERATURE,
    streaming=True,
    thinking_enabled=False,
)

# Formatter model: converts draft replies into {"messages": [...]}.
structured_reply_llm = create_llm(
    model=ACTIVE_LLM["chat_model"],
    streaming=False,
    json_mode=True,
    thinking_enabled=bool_env("AURA_STRUCTURED_LLM_THINKING_ENABLED", ACTIVE_PROVIDER == "deepseek"),
    reasoning_effort=AURA_LLM_REASONING_EFFORT,
)

# Memory model: memory write, deduplication, and merge decisions.
memory_judge_llm = create_llm(
    model=ACTIVE_LLM["judge_model"],
    temperature=0,
    json_mode=True,
    thinking_enabled=False,
)

# Emotion model: produces tone guidance for the main chat model.
emotion_judge_llm = create_llm(
    model=ACTIVE_LLM["judge_model"],
    temperature=0.1,
    json_mode=True,
    thinking_enabled=False,
)
