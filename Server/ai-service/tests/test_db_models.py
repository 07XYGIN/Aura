import sys
import unittest
from pathlib import Path

from pgvector.sqlalchemy import Vector
from sqlalchemy import SmallInteger
from sqlalchemy.dialects.postgresql import JSON

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models import (
    Base,
    BashGameMove,
    BashGameSession,
    CompanionPet,
    LangchainPgCollection,
    LangchainPgEmbedding,
    ProactiveMessage,
    PetEvent,
    Users,
)


class DbModelsTest(unittest.TestCase):
    def test_models_only_cover_active_business_tables(self):
        self.assertEqual(
            {
                "users",
                "self_changelog_entry",
                "proactive_message",
                "bash_game_session",
                "bash_game_move",
                "companion_pet",
                "pet_event",
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
                "uq_bash_game_active_user",
                "idx_bash_game_user_created",
                "idx_bash_move_session_created",
                "idx_pet_event_pet_occurred",
                "ix_cmetadata_gin",
            },
            index_names,
        )

    def test_proactive_message_no_longer_depends_on_notification_plan(self):
        self.assertNotIn("notification_plan_id", ProactiveMessage.__table__.c)
        foreign_keys = list(ProactiveMessage.__table__.c.user_id.foreign_keys)
        self.assertEqual(len(foreign_keys), 1)
        self.assertEqual(foreign_keys[0].target_fullname, "users.id")

    def test_bash_models_preserve_user_ownership_and_move_history(self):
        """游戏会话应归属用户，行动应随会话级联删除。"""

        game_user_fk = list(BashGameSession.__table__.c.user_id.foreign_keys)
        move_session_fk = list(BashGameMove.__table__.c.session_id.foreign_keys)
        self.assertEqual(game_user_fk[0].target_fullname, "users.id")
        self.assertEqual(game_user_fk[0].ondelete, "CASCADE")
        self.assertEqual(move_session_fk[0].target_fullname, "bash_game_session.id")
        self.assertEqual(move_session_fk[0].ondelete, "CASCADE")

    def test_pet_models_preserve_single_ownership_and_event_history(self):
        """共同宠物应归属用户，事件应随宠物级联删除。"""

        pet_user_fk = list(CompanionPet.__table__.c.user_id.foreign_keys)
        event_pet_fk = list(PetEvent.__table__.c.pet_id.foreign_keys)
        self.assertEqual(pet_user_fk[0].target_fullname, "users.id")
        self.assertEqual(pet_user_fk[0].ondelete, "CASCADE")
        self.assertEqual(event_pet_fk[0].target_fullname, "companion_pet.id")
        self.assertEqual(event_pet_fk[0].ondelete, "CASCADE")


if __name__ == "__main__":
    unittest.main()
