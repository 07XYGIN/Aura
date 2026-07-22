import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.memory import service as term_memory


class FakeStore:
    def __init__(self, results=None):
        self.results = results or []
        self.added_documents = []

    def similarity_search_with_relevance_scores(self, *args, **kwargs):
        return self.results

    def add_documents(self, documents):
        self.added_documents.extend(documents)


class MemoryServiceTest(unittest.TestCase):
    def test_rank_memory_results_drops_below_threshold(self):
        doc = Document(page_content="用户喜欢蛋糕", metadata={"memory_scope": "long"})

        with patch.object(term_memory, "MEMORY_RELEVANCE_THRESHOLD", 0.6):
            ranked = term_memory.rank_memory_results([(doc, 0.59)], "long")

        self.assertEqual(ranked, [])

    def test_rank_memory_results_penalizes_recent_long_memory(self):
        now = datetime(2026, 6, 30, 10, 0)
        doc = Document(
            page_content="用户喜欢蛋糕",
            metadata={
                "memory_scope": "long",
                "last_recalled_at": (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M"),
            },
        )

        with (
            patch.object(term_memory, "MEMORY_RELEVANCE_THRESHOLD", 0.6),
            patch.object(term_memory, "LONG_MEMORY_RECALL_COOLDOWN_MINUTES", 180),
            patch.object(term_memory, "LONG_MEMORY_COOLDOWN_BYPASS_THRESHOLD", 0.85),
            patch.object(term_memory, "LONG_MEMORY_COOLDOWN_PENALTY", 0.25),
        ):
            ranked = term_memory.rank_memory_results([(doc, 0.7)], "long", now=now)

        self.assertEqual(ranked, [])

    def test_rank_memory_results_keeps_high_relevance_during_cooldown(self):
        now = datetime(2026, 6, 30, 10, 0)
        doc = Document(
            page_content="用户喜欢蛋糕",
            metadata={
                "memory_scope": "long",
                "last_recalled_at": (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M"),
            },
        )

        with (
            patch.object(term_memory, "MEMORY_RELEVANCE_THRESHOLD", 0.6),
            patch.object(term_memory, "LONG_MEMORY_RECALL_COOLDOWN_MINUTES", 180),
            patch.object(term_memory, "LONG_MEMORY_COOLDOWN_BYPASS_THRESHOLD", 0.85),
            patch.object(term_memory, "LONG_MEMORY_COOLDOWN_PENALTY", 0.25),
        ):
            ranked = term_memory.rank_memory_results([(doc, 0.9)], "long", now=now)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].page_content, "用户喜欢蛋糕")

    def test_build_long_memory_metadata_initializes_recall_marker(self):
        metadata = term_memory.build_memory_metadata(
            user_id="user-1",
            title="偏好",
            create_time="2026-06-30 10:00",
            memory_scope="long",
        )

        self.assertEqual(metadata["memory_scope"], "long")
        self.assertIn("memory_key", metadata)
        self.assertIsNone(metadata["last_recalled_at"])

    def test_build_mid_memory_metadata_initializes_recall_count(self):
        metadata = term_memory.build_memory_metadata(
            user_id="user-1",
            title="recent",
            create_time="2026-06-30 10:00",
            memory_scope="mid",
        )

        self.assertEqual(metadata["memory_scope"], "mid")
        self.assertEqual(metadata["recall_count"], 0)
        self.assertEqual(metadata["forget_after_days"], term_memory.MEDIUM_MEMORY_FORGET_DAYS)

    def test_superseded_memory_is_not_retrievable(self):
        self.assertFalse(term_memory.is_memory_retrievable({"status": "superseded"}, "long"))
        self.assertFalse(term_memory.is_memory_retrievable({"status": "superseded"}, "mid"))

    def test_promoted_mid_memory_is_not_retrievable(self):
        self.assertFalse(term_memory.is_memory_retrievable({"promoted_to_long": True}, "mid"))

    def test_list_memories_exposes_management_fields(self):
        row = {
            "id": "row-1",
            "document": "content",
            "cmetadata": {
                "title": "title",
                "memory_key": "key-1",
                "status": "superseded",
                "superseded_by": "key-2",
            },
        }

        with patch.object(term_memory, "fetch_memory_rows", return_value=[row]):
            page = term_memory.list_memories_by_user(
                user_id="user-1",
                memory_scope="long",
                include_inactive=True,
            )

        item = page["items"][0]
        self.assertEqual(item["memory_key"], "key-1")
        self.assertEqual(item["status"], "superseded")
        self.assertEqual(item["superseded_by"], "key-2")
        self.assertFalse(item["is_retrievable"])

    def test_save_long_memory_duplicate_touches_existing_without_adding(self):
        existing = Document(page_content="I have a cat named Nian Gao.", metadata={"memory_key": "old-key"})
        store = FakeStore(results=[(existing, 0.91)])
        metadata = {
            "user_id": "user-1",
            "title": "cat",
            "create_time": "2026-06-30 10:00",
            "memory_scope": "long",
            "memory_key": "new-key",
        }

        with (
            patch.object(term_memory, "get_memory_vector_store", return_value=store),
            patch.object(term_memory, "judge_memory_dedup", return_value={"decision": "duplicate", "confidence": 0.9, "reason": "same"}),
            patch.object(term_memory, "touch_memory_keys") as touch_memory_keys,
        ):
            result = term_memory.save_long_memory("user-1", "I have a cat named Nian Gao.", metadata)

        self.assertEqual(result, "old-key")
        self.assertEqual(store.added_documents, [])
        touch_memory_keys.assert_called_once_with(
            user_id="user-1",
            memory_keys=["old-key"],
            collection_name=term_memory.LONG_TERM_COLLECTION_NAME,
        )

    def test_save_long_memory_update_supersedes_top_match(self):
        existing = Document(page_content="I work at Company A.", metadata={"memory_key": "old-key"})
        store = FakeStore(results=[(existing, 0.88)])
        metadata = {
            "user_id": "user-1",
            "title": "work",
            "create_time": "2026-06-30 10:00",
            "memory_scope": "long",
            "memory_key": "new-key",
        }

        with (
            patch.object(term_memory, "get_memory_vector_store", return_value=store),
            patch.object(term_memory, "judge_memory_dedup", return_value={"decision": "update", "confidence": 0.86, "reason": "job changed"}),
            patch.object(term_memory, "mark_memory_superseded") as mark_memory_superseded,
        ):
            result = term_memory.save_long_memory("user-1", "I now work at Company B.", metadata)

        self.assertEqual(result, "new-key")
        self.assertEqual(len(store.added_documents), 1)
        self.assertEqual(store.added_documents[0].metadata["supersedes"], "old-key")
        mark_memory_superseded.assert_called_once_with(
            user_id="user-1",
            memory_key="old-key",
            superseded_by="new-key",
            reason="job changed",
        )

    def test_touch_recalled_memories_only_updates_recall_metadata(self):
        doc = Document(page_content="x", metadata={"memory_key": "key-1"})

        with patch.object(term_memory, "touch_memory_keys") as touch_memory_keys:
            term_memory.touch_recalled_memories("user-1", [doc], term_memory.LONG_TERM_COLLECTION_NAME)

        touch_memory_keys.assert_called_once_with(
            user_id="user-1",
            memory_keys=["key-1"],
            collection_name=term_memory.LONG_TERM_COLLECTION_NAME,
        )
    def test_touching_mid_memory_does_not_promote_it_automatically(self):
        doc = Document(page_content="x", metadata={"memory_key": "key-1"})

        with (
            patch.object(term_memory, "touch_memory_keys") as touch_memory_keys,
            patch.object(term_memory, "promote_mid_term_memories") as promote_mid_term_memories,
        ):
            term_memory.touch_recalled_memories("user-1", [doc], term_memory.MEDIUM_TERM_COLLECTION_NAME)

        touch_memory_keys.assert_called_once_with(
            user_id="user-1",
            memory_keys=["key-1"],
            collection_name=term_memory.MEDIUM_TERM_COLLECTION_NAME,
        )
        promote_mid_term_memories.assert_not_called()

    def test_promote_mid_term_memories_saves_long_and_marks_mid(self):
        row = {
            "id": "row-1",
            "document": "User is preparing for an interview this week.",
            "cmetadata": {
                "memory_key": "mid-key",
                "title": "interview",
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "recall_count": 3,
                "last_recalled_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
        }

        with (
            patch.object(term_memory, "fetch_promotable_mid_memory_rows", return_value=[row]),
            patch.object(term_memory, "save_memory", return_value="long-key") as save_memory,
            patch.object(term_memory, "mark_mid_memory_promoted") as mark_mid_memory_promoted,
        ):
            term_memory.promote_mid_term_memories("user-1", ["mid-key"])

        save_memory.assert_called_once()
        _, kwargs = save_memory.call_args
        self.assertEqual(kwargs["memory_scope"], "long")
        self.assertEqual(kwargs["extra_metadata"]["promoted_from_mid_key"], "mid-key")
        mark_mid_memory_promoted.assert_called_once_with(
            user_id="user-1",
            memory_key="mid-key",
            promoted_memory_key="long-key",
        )

    def test_cosine_similarity_handles_same_and_orthogonal_vectors(self):
        self.assertEqual(term_memory.cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        self.assertEqual(term_memory.cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)
        self.assertEqual(term_memory.cosine_similarity([1.0], [1.0, 0.0]), 0.0)

    def test_normalize_embedding_accepts_vector_like_values(self):
        class VectorLike:
            def tolist(self):
                return [1, "2.5", 3.0]

        self.assertEqual(term_memory.normalize_embedding(VectorLike()), [1.0, 2.5, 3.0])
        self.assertEqual(term_memory.normalize_embedding((1, 2)), [1.0, 2.0])
        self.assertEqual(term_memory.normalize_embedding("not-a-vector"), [])

    def test_build_similarity_clusters_groups_and_strips_internal_fields(self):
        memories = [
            {
                "memory_key": "key-a",
                "user_id": "user-1",
                "title": "hotpot",
                "content": "Likes eating hotpot with friends.",
                "create_time": "2026-07-01 10:00",
                "embedding": [1.0, 0.0],
                "metadata": {"private": True},
            },
            {
                "memory_key": "key-b",
                "user_id": "user-1",
                "title": "hotpot mood",
                "content": "Enjoyed a hotpot dinner with friends.",
                "create_time": "2026-07-02 10:00",
                "embedding": [0.99, 0.01],
                "metadata": {"private": True},
            },
            {
                "memory_key": "key-c",
                "user_id": "user-1",
                "title": "work",
                "content": "Preparing for an interview.",
                "create_time": "2026-07-03 10:00",
                "embedding": [0.0, 1.0],
                "metadata": {"private": True},
            },
        ]

        clusters = term_memory.build_similarity_clusters(memories, threshold=0.95)

        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["memory_keys"] if "memory_keys" in clusters[0] else ["key-a", "key-b"], ["key-a", "key-b"])
        self.assertEqual([memory["memory_key"] for memory in clusters[0]["memories"]], ["key-a", "key-b"])
        self.assertNotIn("embedding", clusters[0]["memories"][0])
        self.assertNotIn("metadata", clusters[0]["memories"][0])

    def test_apply_memory_merge_saves_merged_memory_and_supersedes_sources(self):
        rows = [
            {"memory_key": "key-a", "confidence": 0.7, "content": "喜欢和朋友吃火锅。"},
            {"memory_key": "key-b", "confidence": 0.9, "content": "吃火锅不太能吃辣。"},
        ]

        with (
            patch.object(term_memory, "fetch_long_memory_entries_by_keys", return_value=rows),
            patch.object(term_memory, "save_memory", return_value="merged-key") as save_memory,
            patch.object(term_memory, "mark_memory_superseded") as mark_memory_superseded,
        ):
            result = term_memory.apply_memory_merge(
                user_id="user-1",
                memory_keys=["key-a", "key-b", "key-a"],
                merged_title="火锅偏好",
                merged_content="喜欢和朋友吃火锅，但不太能吃辣。",
                reason="manual_review",
            )

        self.assertEqual(result["memory_key"], "merged-key")
        self.assertEqual(result["merged_from"], ["key-a", "key-b"])
        save_memory.assert_called_once()
        _, kwargs = save_memory.call_args
        self.assertTrue(kwargs["skip_dedup"])
        self.assertEqual(kwargs["memory_scope"], "long")
        self.assertEqual(kwargs["confidence"], 0.9)
        self.assertEqual(kwargs["extra_metadata"]["merged_from"], ["key-a", "key-b"])
        self.assertEqual(mark_memory_superseded.call_count, 2)
        mark_memory_superseded.assert_any_call(
            user_id="user-1",
            memory_key="key-a",
            superseded_by="merged-key",
            reason="manual_review",
        )
        mark_memory_superseded.assert_any_call(
            user_id="user-1",
            memory_key="key-b",
            superseded_by="merged-key",
            reason="manual_review",
        )

    def test_list_topic_memory_merge_candidates_requires_two_relevant_memories(self):
        store = FakeStore(results=[
            (
                Document(
                    page_content="今天调整了 Aura 的人设提示词。",
                    metadata={
                        "memory_key": "key-a",
                        "user_id": "user-1",
                        "title": "人设调整",
                        "create_time": "2026-07-04 10:00",
                    },
                ),
                0.8,
            )
        ])

        with patch.object(term_memory, "get_memory_vector_store", return_value=store):
            result = term_memory.list_topic_memory_merge_candidates(
                user_id="user-1",
                topic_query="今天 Aura 项目改动",
            )

        self.assertEqual(result["items"], [])
        self.assertEqual(result["total"], 0)

    def test_list_topic_memory_merge_candidates_merges_topic_matches(self):
        store = FakeStore(results=[
            (
                Document(
                    page_content="今天调整了 Aura 的人设提示词。",
                    metadata={
                        "memory_key": "key-a",
                        "user_id": "user-1",
                        "title": "人设调整",
                        "create_time": "2026-07-04 10:00",
                    },
                ),
                0.82,
            ),
            (
                Document(
                    page_content="今天把情绪检测从关键词改成 LLM 判断。",
                    metadata={
                        "memory_key": "key-b",
                        "user_id": "user-1",
                        "title": "情绪检测",
                        "create_time": "2026-07-04 11:00",
                    },
                ),
                0.76,
            ),
        ])

        with (
            patch.object(term_memory, "get_memory_vector_store", return_value=store),
            patch.object(
                term_memory,
                "merge_memory_contents",
                return_value={
                    "title": "Aura 项目改动",
                    "content": "今天集中调整 Aura 项目，包括人设提示词和情绪检测。",
                    "reason": "同一主题下的项目迭代线索",
                },
            ) as merge_memory_contents,
        ):
            result = term_memory.list_topic_memory_merge_candidates(
                user_id="user-1",
                topic_query="今天 Aura 项目改动",
                threshold=0.52,
            )

        self.assertEqual(result["total"], 1)
        item = result["items"][0]
        self.assertEqual(item["memory_keys"], ["key-a", "key-b"])
        self.assertEqual(item["suggested_title"], "Aura 项目改动")
        merge_memory_contents.assert_called_once()
        _, kwargs = merge_memory_contents.call_args
        self.assertEqual(kwargs["topic_query"], "今天 Aura 项目改动")


if __name__ == "__main__":
    unittest.main()
