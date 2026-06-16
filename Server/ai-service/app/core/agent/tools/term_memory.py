from typing import Any

import psycopg
from psycopg.rows import dict_row
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector

from app.core.config import SYNC_DATABASE_URL

MEMORY_COLLECTION_NAME = "aura"

embeddings = OllamaEmbeddings(
    model="nomic-embed-text:latest"
)


def get_memory_vector_store() -> PGVector:
    return PGVector(
        embeddings=embeddings,
        collection_name=MEMORY_COLLECTION_NAME,
        connection=SYNC_DATABASE_URL,
        use_jsonb=True,
    )


def save_memory(user_id: str, content: str, title: str, create_time: str):
    store = get_memory_vector_store()
    doc = Document(
        page_content=content,
        metadata={
            "user_id": user_id,
            "title": title,
            "create_time": create_time,
        }
    )
    store.add_documents([doc])


def search_memory(user_id: str, query: str, k: int = 5) -> list[Document]:
    store = get_memory_vector_store()
    return store.similarity_search(
        query,
        k=k,
        filter={"user_id": user_id}
    )


def list_memories_by_user(user_id: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size

    with psycopg.connect(SYNC_DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM langchain_pg_embedding e
                JOIN langchain_pg_collection c ON e.collection_id = c.uuid
                WHERE c.name = %(collection_name)s
                  AND e.cmetadata ->> 'user_id' = %(user_id)s
                """,
                {
                    "collection_name": MEMORY_COLLECTION_NAME,
                    "user_id": user_id,
                },
            )
            total = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT e.id, e.document, e.cmetadata
                FROM langchain_pg_embedding e
                JOIN langchain_pg_collection c ON e.collection_id = c.uuid
                WHERE c.name = %(collection_name)s
                  AND e.cmetadata ->> 'user_id' = %(user_id)s
                ORDER BY e.cmetadata ->> 'create_time' DESC NULLS LAST, e.id DESC
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                {
                    "collection_name": MEMORY_COLLECTION_NAME,
                    "user_id": user_id,
                    "limit": page_size,
                    "offset": offset,
                },
            )
            rows = cursor.fetchall()

    items = []
    for row in rows:
        metadata = dict(row["cmetadata"] or {})
        metadata.setdefault("content", row["document"])
        items.append(
            {
                "id": row["id"],
                "metadata": metadata,
                "page_content": row["document"],
                "type": "Document",
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": offset + len(items) < total,
    }
