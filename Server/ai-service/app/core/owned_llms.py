from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


# Keep every owned OpenAI-compatible model in one place.
# Switch AURA_LLM_PROVIDER to move Aura between these models.

LONGCAT = {
    "provider": "longcat",
    "api_key": os.getenv("LONGCAT_API_KEY", ""),
    "base_url": os.getenv("LONGCAT_BASE_URL", "https://api.longcat.chat/openai"),
    "chat_model": os.getenv("LONGCAT_MODEL", "LongCat-2.0"),
    "judge_model": os.getenv("LONGCAT_MEMORY_MODEL", os.getenv("LONGCAT_MODEL", "LongCat-2.0")),
    "thinking": True,
    "json_mode": False,
}

DEEPSEEK = {
    "provider": "deepseek",
    "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
    "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    "chat_model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
    "judge_model": os.getenv("DEEPSEEK_MEMORY_MODEL", "deepseek-v4-flash"),
    "thinking": True,
    "json_mode": True,
}

DASHSCOPE = {
    "provider": "dashscope",
    "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
    "base_url": os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "chat_model": os.getenv("DASHSCOPE_MODEL", "qwen-plus"),
    "judge_model": os.getenv("DASHSCOPE_MEMORY_MODEL", os.getenv("DASHSCOPE_MODEL", "qwen-plus")),
    "thinking": False,
    "json_mode": True,
}

OWNED_LLMS = {
    "longcat": LONGCAT,
    "deepseek": DEEPSEEK,
    "dashscope": DASHSCOPE,
}
