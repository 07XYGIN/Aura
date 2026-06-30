import sys
import unittest
from pathlib import Path

from pgvector.sqlalchemy import Vector

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models import LangchainPgEmbedding, MemoryItem


class DbModelsTest(unittest.TestCase):
    def test_memory_item_embedding_uses_pgvector_type(self):
        embedding_type = MemoryItem.__table__.c.embedding.type

        self.assertIsInstance(embedding_type, Vector)
        self.assertEqual(embedding_type.dim, 768)

    def test_langchain_embedding_uses_pgvector_type(self):
        embedding_type = LangchainPgEmbedding.__table__.c.embedding.type

        self.assertIsInstance(embedding_type, Vector)


if __name__ == "__main__":
    unittest.main()
