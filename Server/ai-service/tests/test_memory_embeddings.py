import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.memory import service
from app.core.memory.embeddings import MemoryEmbeddingsUnavailable
from app.routers.memory import get_current_user_id
from main import create_app


class MemoryEmbeddingsTest(unittest.TestCase):
    def test_writes_fail_before_opening_a_vector_store(self):
        for scope, skip_dedup in (("long", False), ("long", True), ("mid", False)):
            with self.subTest(scope=scope, skip_dedup=skip_dedup):
                with patch.object(service, "PGVector") as vector_store:
                    with self.assertRaises(MemoryEmbeddingsUnavailable):
                        service.save_memory(
                            user_id="user-1",
                            content="A saved preference",
                            title="Preference",
                            create_time="2026-10-10 12:00",
                            memory_scope=scope,
                            skip_dedup=skip_dedup,
                        )
                vector_store.assert_not_called()

    def test_chat_memory_context_handles_unavailable_provider(self):
        with patch.object(service, "PGVector") as vector_store:
            context = service.format_memory_context("user-1", "favorite food")

        self.assertIn("暂未接入", context)
        self.assertNotIn("没有检索到可引用", context)
        vector_store.assert_not_called()

    def test_memory_catalog_still_reads_existing_documents(self):
        rows = [{"id": "memory-1", "document": "Saved fact", "cmetadata": {"status": "active"}}]
        with (
            patch.object(service, "fetch_memory_rows", return_value=rows),
            patch.object(service, "get_memory_embeddings") as get_embeddings,
        ):
            docs = service.search_memory_collection("user-1", "所有记忆", 5, "aura", "long")
            page = service.list_memories_by_user("user-1")

        self.assertEqual([doc.page_content for doc in docs], ["Saved fact"])
        self.assertEqual(page["items"][0]["page_content"], "Saved fact")
        get_embeddings.assert_not_called()


class MemoryEmbeddingsApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_semantic_search_returns_503_without_database_or_model_calls(self):
        app = create_app()
        app.dependency_overrides[get_current_user_id] = lambda: "user-1"
        with patch.object(service, "PGVector") as vector_store:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/memory/getMemory", params={"query": "favorite food"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], 503)
        self.assertIsNone(response.json()["data"])
        self.assertIn("暂未接入", response.json()["message"])
        vector_store.assert_not_called()
