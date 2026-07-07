import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.core.owned_llms import DEEPSEEK, DEEPSEEK_FLASH, DZMM_APEX_SIGMA_16K, LONGCAT

load_dotenv()


# Change these four lines when one task should use a different model.
CHAT_MODEL = DZMM_APEX_SIGMA_16K
STRUCTURED_REPLY_MODEL = LONGCAT
MEMORY_JUDGE_MODEL = DEEPSEEK_FLASH
EMOTION_JUDGE_MODEL = DEEPSEEK_FLASH
"""
CHAT_MODEL：主对话模型
structured_reply_llm：把回复整理成 Aura 需要的 JSON 消息数组
memory_judge_llm：判断是否写入记忆、合并记忆
emotion_judge_llm：判断情绪上下文
"""

AURA_LLM_TEMPERATURE = 1.0
AURA_LLM_REASONING_EFFORT = "high"

DEEPSEEK_MODELS = (DEEPSEEK, DEEPSEEK_FLASH)


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
    if "max_tokens" in model_config:
        kwargs["max_tokens"] = model_config["max_tokens"]
    if json_mode and model_config in DEEPSEEK_MODELS:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    if model_config in (LONGCAT, *DEEPSEEK_MODELS):
        kwargs["extra_body"] = {"thinking": {"type": "enabled" if thinking_enabled else "disabled"}}
    if "top_p" in model_config or "repetition_penalty" in model_config:
        kwargs["extra_body"] = {
            **(kwargs.get("extra_body") or {}),
            **{name: model_config[name] for name in ("top_p", "repetition_penalty") if name in model_config},
        }
    if model_config in DEEPSEEK_MODELS and thinking_enabled:
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
    thinking_enabled=STRUCTURED_REPLY_MODEL in DEEPSEEK_MODELS,
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
