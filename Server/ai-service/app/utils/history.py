import psycopg
from psycopg_pool import ConnectionPool
from langchain_postgres import PostgresChatMessageHistory
from app.core.config import SYNC_DATABASE_URL
connection_pool = ConnectionPool(conninfo=SYNC_DATABASE_URL, open=False)
def get_session_history(session_id: str)-> PostgresChatMessageHistory:
    conn = psycopg.connect(SYNC_DATABASE_URL, autocommit=True)
    return PostgresChatMessageHistory(
    "chat_history", 
    session_id, 
    sync_connection=conn
    )