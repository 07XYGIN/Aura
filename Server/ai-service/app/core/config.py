import os

from dotenv import load_dotenv

from app.core.llms import (
    AURA_LLM_REASONING_EFFORT,
    AURA_LLM_TEMPERATURE,
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
    "AURA_LLM_TEMPERATURE",
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
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, parsed)


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
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
print(SYNC_DATABASE_URL)