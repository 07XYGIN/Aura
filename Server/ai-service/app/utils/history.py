import psycopg
from langchain_postgres import PostgresChatMessageHistory

from app.core.config import SYNC_DATABASE_URL


def clear_session_history(session_id: str) -> None:
    with psycopg.connect(SYNC_DATABASE_URL, autocommit=True) as conn:
        history = PostgresChatMessageHistory(
            "chat_history",
            session_id,
            sync_connection=conn,
        )
        history.clear()
