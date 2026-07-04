import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def int_env(name: str, default: int, minimum: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, parsed)


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
DEEPSEEK_MEMORY_MODEL = os.getenv("DEEPSEEK_MEMORY_MODEL", "deepseek-v4-flash")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
AURA_PROACTIVE_SCHEDULER_ENABLED = os.getenv("AURA_PROACTIVE_SCHEDULER_ENABLED", "true").strip().lower() not in {
    "0",
    "false",
    "no",
}
AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS = int_env("AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS", 15, 5)
AURA_PROACTIVE_SCHEDULER_LOOKAHEAD_HOURS = int_env("AURA_PROACTIVE_SCHEDULER_LOOKAHEAD_HOURS", 24, 1)
AURA_LLM_TEMPERATURE = float(os.getenv("AURA_LLM_TEMPERATURE", "1"))
DEEPSEEK_REASONING_EFFORT = os.getenv("DEEPSEEK_REASONING_EFFORT", "high").strip().lower()
if DEEPSEEK_REASONING_EFFORT not in {"high", "max"}:
    DEEPSEEK_REASONING_EFFORT = "high"


def ensure_deepseek_api_key() -> None:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is required in Server/ai-service/.env")


llm = ChatOpenAI(
    model=DEEPSEEK_MODEL,
    api_key=DEEPSEEK_API_KEY or "missing-deepseek-api-key",
    base_url=DEEPSEEK_BASE_URL,
    temperature=AURA_LLM_TEMPERATURE,
    streaming=True,
    stream_usage=False,
    extra_body={"thinking": {"type": "disabled"}},
)

structured_reply_llm = ChatOpenAI(
    model=DEEPSEEK_MODEL,
    api_key=DEEPSEEK_API_KEY or "missing-deepseek-api-key",
    base_url=DEEPSEEK_BASE_URL,
    streaming=False,
    stream_usage=False,
    reasoning_effort=DEEPSEEK_REASONING_EFFORT,
    model_kwargs={"response_format": {"type": "json_object"}},
    extra_body={"thinking": {"type": "enabled"}},
)

memory_judge_llm = ChatOpenAI(
    model=DEEPSEEK_MEMORY_MODEL,
    api_key=DEEPSEEK_API_KEY or "missing-deepseek-api-key",
    base_url=DEEPSEEK_BASE_URL,
    temperature=0,
    model_kwargs={"response_format": {"type": "json_object"}},
    extra_body={"thinking": {"type": "disabled"}},
)

HOST = os.getenv('DB_HOST')
PORT = os.getenv('DB_PORT')
NAME = os.getenv('DB_NAME')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')


PG_DATABASE_URL = f'postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}'
SYNC_DATABASE_URL = f'postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}'
