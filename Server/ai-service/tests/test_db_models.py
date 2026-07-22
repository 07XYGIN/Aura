import sys
import unittest
from pathlib import Path

from pgvector.sqlalchemy import Vector
from sqlalchemy import SmallInteger
from sqlalchemy.dialects.postgresql import JSON

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models import Base, LangchainPgCollection, LangchainPgEmbedding, ProactiveMessage, Users


class DbModelsTest(unittest.TestCase):
    def test_models_only_cover_active_business_tables(self):
        self.assertEqual(
            {
                "users",
                "self_changelog_entry",
                "proactive_message",
                "langchain_pg_collection",
                "langchain_pg_embedding",
            },
            set(Base.metadata.tables),
        )

    def test_langchain_embedding_uses_pgvector_type(self):
        self.assertIsInstance(LangchainPgEmbedding.__table__.c.embedding.type, Vector)

    def test_model_types_match_library_and_existing_schema(self):
        self.assertIsInstance(Users.__table__.c.sex.type, SmallInteger)
        self.assertIsInstance(LangchainPgCollection.__table__.c.cmetadata.type, JSON)

    def test_active_non_constraint_indexes_are_modeled(self):
        index_names = {
            index.name
            for table in Base.metadata.tables.values()
            for index in table.indexes
        }
        self.assertEqual(
            {
                "idx_self_changelog_unreacted",
                "idx_self_changelog_occurred_at",
                "idx_proactive_message_user_schedule",
                "ix_cmetadata_gin",
            },
            index_names,
        )

    def test_proactive_message_no_longer_depends_on_notification_plan(self):
        self.assertNotIn("notification_plan_id", ProactiveMessage.__table__.c)
        foreign_keys = list(ProactiveMessage.__table__.c.user_id.foreign_keys)
        self.assertEqual(len(foreign_keys), 1)
        self.assertEqual(foreign_keys[0].target_fullname, "users.id")


if __name__ == "__main__":
    unittest.main()
