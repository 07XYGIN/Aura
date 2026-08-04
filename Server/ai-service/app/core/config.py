import os

from dotenv import load_dotenv

from app.core.llms import (
    AURA_LLM_REASONING_EFFORT,
    AURA_LLM_ENABLE_THINKING,
    AURA_LLM_TEMPERATURE,
    AURA_LLM_TOP_P,
    CHAT_MODEL,
    EMOTION_JUDGE_MODEL,
    MEMORY_JUDGE_MODEL,
    STRUCTURED_REPLY_MODEL,
    emotion_judge_llm,
    llm,
    memory_judge_llm,
    structured_reply_llm,
)

load_dotenv()

__all__ = [
    "AURA_LLM_REASONING_EFFORT",
    "AURA_LLM_ENABLE_THINKING",
    "AURA_LLM_TEMPERATURE",
    "AURA_LLM_TOP_P",
    "CHAT_MODEL",
    "EMOTION_JUDGE_MODEL",
    "MEMORY_JUDGE_MODEL",
    "STRUCTURED_REPLY_MODEL",
    "emotion_judge_llm",
    "llm",
    "memory_judge_llm",
    "structured_reply_llm",
]


def int_env(name: str, default: int, minimum: int) -> int:
    """读取整数环境变量，缺失或无效时使用默认值，并保证不低于下限。"""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, parsed)


def bool_env(name: str, default: bool = False) -> bool:
    """读取布尔环境变量，无法识别时使用默认值。"""
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
AURA_TIMEZONE = os.getenv("AURA_TIMEZONE", "Asia/Shanghai").strip() or "Asia/Shanghai"
AURA_CITY_ADCODE = os.getenv("AURA_CITY_ADCODE", "").strip() or None
AURA_OPTIONAL_ACTIVITIES_ENABLED = bool_env("AURA_OPTIONAL_ACTIVITIES_ENABLED", False)
AURA_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "AURA_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
AURA_PROACTIVE_SCHEDULER_ENABLED = os.getenv("AURA_PROACTIVE_SCHEDULER_ENABLED", "true").strip().lower() not in {
    "0",
    "false",
    "no",
}
AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS = int_env("AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS", 600, 5)
AURA_PROACTIVE_SCHEDULER_LOOKAHEAD_HOURS = int_env("AURA_PROACTIVE_SCHEDULER_LOOKAHEAD_HOURS", 24, 1)

HOST = os.getenv('DB_HOST')
PORT = os.getenv('DB_PORT')
NAME = os.getenv('DB_NAME')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')


PG_DATABASE_URL = f'postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}'


SYNC_DATABASE_URL = f'postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}'
