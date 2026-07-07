import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.core.owned_llms import DEEPSEEK, LONGCAT

load_dotenv()


# Switch the active model here:
# CURRENT_LLM = DEEPSEEK
CURRENT_LLM = LONGCAT

ACTIVE_LLM = CURRENT_LLM
ACTIVE_PROVIDER = "longcat" if CURRENT_LLM == LONGCAT else "deepseek"
AURA_LLM_TEMPERATURE = 1.0
AURA_LLM_REASONING_EFFORT = "high"


def current_api_key() -> str:
    if CURRENT_LLM == LONGCAT:
        return os.getenv("LONGCAT_API_KEY", "")
    return os.getenv("DEEPSEEK_API_KEY", "")


def create_llm(
    model: str,
    *,
    temperature: float | None = None,
    streaming: bool = False,
    json_mode: bool = False,
    thinking_enabled: bool = False,
) -> ChatOpenAI:
    kwargs: dict[str, object] = {
        "model": model,
        "api_key": current_api_key(),
        "base_url": CURRENT_LLM["base_url"],
        "streaming": streaming,
        "stream_usage": False,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if json_mode and CURRENT_LLM == DEEPSEEK:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    if CURRENT_LLM in (LONGCAT, DEEPSEEK):
        kwargs["extra_body"] = {"thinking": {"type": "enabled" if thinking_enabled else "disabled"}}
    if CURRENT_LLM == DEEPSEEK and thinking_enabled:
        kwargs["reasoning_effort"] = AURA_LLM_REASONING_EFFORT
    return ChatOpenAI(**kwargs)


llm = create_llm(
    CURRENT_LLM["chat_model"],
    temperature=AURA_LLM_TEMPERATURE,
    streaming=True,
)

structured_reply_llm = create_llm(
    CURRENT_LLM["chat_model"],
    json_mode=True,
    thinking_enabled=CURRENT_LLM == DEEPSEEK,
)

memory_judge_llm = create_llm(
    CURRENT_LLM["judge_model"],
    temperature=0,
    json_mode=True,
)

emotion_judge_llm = create_llm(
    CURRENT_LLM["judge_model"],
    temperature=0.1,
    json_mode=True,
)
