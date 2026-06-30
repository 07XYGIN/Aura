import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
DEEPSEEK_MEMORY_MODEL = os.getenv("DEEPSEEK_MEMORY_MODEL", "deepseek-v4-flash")
AURA_LLM_TEMPERATURE = float(os.getenv("AURA_LLM_TEMPERATURE", "1"))


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
