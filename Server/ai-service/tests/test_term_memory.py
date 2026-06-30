import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.tools import term_memory


class TermMemoryTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
