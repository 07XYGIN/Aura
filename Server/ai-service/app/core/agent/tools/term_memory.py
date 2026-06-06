from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector

from app.core.config import SYNC_DATABASE_URL

embeddings = OllamaEmbeddings(
    model="nomic-embed-text:latest"
)


def get_memory_vector_store() -> PGVector:
    return PGVector(
        embeddings=embeddings,
        collection_name="aura",
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
