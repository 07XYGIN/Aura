import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

PROVIDERS = {
    "qwen": {
        "model": "qwen3.8-max",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "DASHSCOPE_API_KEY",
        "supports_thinking": True,
    },
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "supports_thinking": False,
    },
    "zhipu": {
        "model": "glm-4.6",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_env": "ZAI_API_KEY",
        "supports_thinking": False,
    },
}

LLM_NAME = os.getenv("AURA_LLM_NAME", "qwen")
if LLM_NAME not in PROVIDERS:
    raise ValueError(f"未知的 AURA_LLM_NAME={LLM_NAME!r}，可选: {list(PROVIDERS)}")


def create_llm(*, temperature=None, top_p=None, streaming=False,
               json_mode=False, thinking=False) -> ChatOpenAI:
    cfg = PROVIDERS[LLM_NAME]
    kwargs = {
        "model": cfg["model"],
        "base_url": cfg["base_url"],
        "api_key": os.getenv(cfg["api_key_env"], ""),
        "streaming": streaming,
        "stream_usage": False,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if top_p is not None:
        kwargs["top_p"] = top_p
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    if cfg["supports_thinking"]:
        # Qwen 的 JSON 模式与 thinking 互斥
        kwargs["extra_body"] = {"enable_thinking": thinking and not json_mode}
    return ChatOpenAI(**kwargs)


llm = create_llm(
    temperature=float(os.getenv("AURA_LLM_TEMPERATURE", 0.7)),
    top_p=0.85,
    streaming=True,
    thinking=os.getenv("AURA_LLM_ENABLE_THINKING", "").lower() in {"1", "true"},
)
structured_reply_llm = create_llm(temperature=0, top_p=0.2, json_mode=True)
memory_judge_llm = create_llm(temperature=0, top_p=0.2, json_mode=True)
emotion_judge_llm = create_llm(temperature=0, top_p=0.2, json_mode=True)

print(llm)