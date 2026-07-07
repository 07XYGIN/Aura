import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.core.owned_llms import DEEPSEEK, GLM, LONGCAT, QWEN_PLUS

load_dotenv()


# Change these four lines when one task should use a different model.
CHAT_MODEL = LONGCAT
STRUCTURED_REPLY_MODEL = LONGCAT
MEMORY_JUDGE_MODEL = LONGCAT
EMOTION_JUDGE_MODEL = LONGCAT

# Example:
# CHAT_MODEL = DEEPSEEK
# STRUCTURED_REPLY_MODEL = LONGCAT
# MEMORY_JUDGE_MODEL = QWEN_PLUS
# EMOTION_JUDGE_MODEL = GLM

AURA_LLM_TEMPERATURE = 1.0
AURA_LLM_REASONING_EFFORT = "high"


def create_llm(
    model_config: dict,
    *,
    temperature: float | None = None,
    streaming: bool = False,
    json_mode: bool = False,
    thinking_enabled: bool = False,
) -> ChatOpenAI:
    kwargs: dict[str, object] = {
        "model": model_config["model"],
        "api_key": os.getenv(model_config["api_key_env"], ""),
        "base_url": model_config["base_url"],
        "streaming": streaming,
        "stream_usage": False,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if json_mode and model_config == DEEPSEEK:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    if model_config in (LONGCAT, DEEPSEEK):
        kwargs["extra_body"] = {"thinking": {"type": "enabled" if thinking_enabled else "disabled"}}
    if model_config == DEEPSEEK and thinking_enabled:
        kwargs["reasoning_effort"] = AURA_LLM_REASONING_EFFORT
    return ChatOpenAI(**kwargs)


llm = create_llm(
    CHAT_MODEL,
    temperature=AURA_LLM_TEMPERATURE,
    streaming=True,
)

structured_reply_llm = create_llm(
    STRUCTURED_REPLY_MODEL,
    json_mode=True,
    thinking_enabled=STRUCTURED_REPLY_MODEL == DEEPSEEK,
)

memory_judge_llm = create_llm(
    MEMORY_JUDGE_MODEL,
    temperature=0,
    json_mode=True,
)

emotion_judge_llm = create_llm(
    EMOTION_JUDGE_MODEL,
    temperature=0.1,
    json_mode=True,
)
