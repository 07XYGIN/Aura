import sys
import unittest
from pathlib import Path
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Numeric, SmallInteger
from sqlalchemy.dialects.postgresql import JSON

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models import (
    Base,
    AuraDailyState,
    AuraSleepCycle,
    AuraThoughtSeed,
    BashGameMove,
    BashGameSession,
    CompanionPet,
    ConditionalMessage,
    ConditionalMessageEvent,
    EmotionalAfterglow,
    FocusSession,
    FocusSessionEvent,
    LangchainPgCollection,
    LangchainPgEmbedding,
    ProactiveMessage,
    PetEvent,
    RelationshipChapter,
    RelationshipItem,
    RelationshipThread,
    RelationshipThreadEvent,
    SharedScene,
    Users,
)


class DbModelsTest(unittest.TestCase):
    def test_models_only_cover_active_business_tables(self):
        self.assertEqual(
            {
                "users",
                "self_changelog_entry",
                "proactive_message",
                "conditional_message",
                "conditional_message_event",
                "focus_session",
                "focus_session_event",
                "relationship_thread",
                "relationship_thread_event",
                "relationship_item",
                "relationship_chapter",
                "aura_daily_state",
                "emotional_afterglow",
                "shared_scene",
                "aura_thought_seed",
                "aura_sleep_cycle",
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
                "idx_proactive_message_claim",
                "idx_conditional_message_time_due",
                "idx_conditional_message_user_status",
                "idx_conditional_message_event_user_time",
                "uq_focus_session_running_user",
                "idx_focus_session_user_created",
                "idx_focus_session_due",
                "idx_focus_session_event_session_time",
                "idx_relationship_thread_user_status_follow_up",
                "idx_relationship_thread_event_thread_occurred",
                "idx_relationship_item_user_type_status",
                "uq_relationship_chapter_current_user",
                "idx_relationship_chapter_user_sequence",
                "idx_aura_daily_state_user_date",
                "idx_emotional_afterglow_user_expires",
                "uq_shared_scene_active_user",
                "idx_shared_scene_user_started",
                "idx_aura_thought_seed_status_eligible",
                "idx_aura_thought_seed_user_created",
                "idx_aura_sleep_cycle_user_date",
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

    def test_proactive_message_models_reliable_outbox_contract(self):
        table = ProactiveMessage.__table__
        self.assertEqual(
            {
                "id",
                "user_id",
                "trigger_type",
                "title",
                "content",
                "scheduled_at",
                "sent_at",
                "dedupe_key",
                "delivery_message_id",
                "attempt_count",
                "claimed_until",
                "last_error",
                "cancelled_at",
                "status",
                "metadata",
                "created_at",
                "updated_at",
            },
            set(table.c.keys()),
        )
        self.assertEqual(table.c.dedupe_key.type.length, 160)
        self.assertTrue(table.c.dedupe_key.nullable)
        self.assertEqual(table.c.delivery_message_id.type.length, 128)
        self.assertFalse(table.c.delivery_message_id.nullable)
        self.assertEqual(table.c.delivery_message_id.server_default.arg.text, "(gen_random_uuid())::text")
        self.assertIsInstance(UUID(table.c.delivery_message_id.default.arg(None)), UUID)
        self.assertFalse(table.c.attempt_count.nullable)
        self.assertEqual(table.c.attempt_count.server_default.arg, "0")
        self.assertTrue(table.c.claimed_until.type.timezone)
        self.assertTrue(table.c.claimed_until.nullable)
        self.assertTrue(table.c.last_error.nullable)
        self.assertTrue(table.c.cancelled_at.type.timezone)
        self.assertTrue(table.c.cancelled_at.nullable)

        constraints = {constraint.name: constraint for constraint in table.constraints}
        self.assertIn("chk_proactive_message_status", constraints)
        self.assertIn("uq_proactive_message_user_dedupe", constraints)
        status_sql = str(constraints["chk_proactive_message_status"].sqltext)
        for status in ("pending", "processing", "sent", "skipped", "failed", "cancelled"):
            self.assertIn(f"'{status}'", status_sql)
        unique_columns = tuple(
            column.name for column in constraints["uq_proactive_message_user_dedupe"].columns
        )
        self.assertEqual(unique_columns, ("user_id", "dedupe_key"))

        claim_index = next(index for index in table.indexes if index.name == "idx_proactive_message_claim")
        self.assertEqual(
            tuple(expression.name for expression in claim_index.expressions),
            ("status", "scheduled_at", "claimed_until"),
        )

    def test_conditional_message_models_match_sealed_lifecycle_contract(self):
        """条件业务状态、outbox 引用和事件 inbox 必须有数据库级边界。"""

        table = ConditionalMessage.__table__
        self.assertEqual(
            {
                "id", "user_id", "message_type", "condition_type", "title", "content",
                "status", "deliver_at", "condition", "unlock_secret_hash", "dedupe_key",
                "outbox_message_id", "source_message_id", "source_turn_id", "triggered_at",
                "delivered_at", "cancelled_at", "expires_at", "version", "metadata",
                "created_at", "updated_at",
            },
            set(table.c.keys()),
        )
        constraints = {constraint.name: constraint for constraint in table.constraints}
        for name in (
            "chk_conditional_message_type",
            "chk_conditional_message_condition_type",
            "chk_conditional_message_status",
            "chk_conditional_message_time_requires_delivery",
            "chk_conditional_message_version",
            "uq_conditional_message_user_dedupe",
        ):
            self.assertIn(name, constraints)
        condition_sql = str(constraints["chk_conditional_message_condition_type"].sqltext)
        for condition_type in ("time", "keyword", "project_status", "github_event", "passphrase"):
            self.assertIn(f"'{condition_type}'", condition_sql)
        status_sql = str(constraints["chk_conditional_message_status"].sqltext)
        for status in ("sealed", "queued", "delivered", "cancelled", "expired", "failed"):
            self.assertIn(f"'{status}'", status_sql)
        self.assertEqual(table.c.status.server_default.arg, "sealed")
        self.assertEqual(table.c.version.server_default.arg, "1")
        self.assertTrue(table.c.deliver_at.type.timezone)
        self.assertTrue(table.c.expires_at.type.timezone)

        user_fk = list(table.c.user_id.foreign_keys)[0]
        outbox_fk = list(table.c.outbox_message_id.foreign_keys)[0]
        self.assertEqual(user_fk.target_fullname, "users.id")
        self.assertEqual(user_fk.ondelete, "CASCADE")
        self.assertEqual(outbox_fk.target_fullname, "proactive_message.id")
        self.assertEqual(outbox_fk.ondelete, "SET NULL")
        self.assertTrue(outbox_fk.deferrable)
        self.assertEqual(outbox_fk.initially, "DEFERRED")

        event_table = ConditionalMessageEvent.__table__
        event_constraints = {constraint.name for constraint in event_table.constraints}
        self.assertTrue(
            {
                "chk_conditional_message_event_type",
                "chk_conditional_message_event_matched_count",
                "uq_conditional_message_event_user_event",
            }.issubset(event_constraints)
        )
        event_user_fk = list(event_table.c.user_id.foreign_keys)[0]
        self.assertEqual(event_user_fk.ondelete, "CASCADE")

    def test_focus_models_preserve_single_running_session_and_event_history(self):
        focus_constraints = {constraint.name for constraint in FocusSession.__table__.constraints}
        event_constraints = {constraint.name for constraint in FocusSessionEvent.__table__.constraints}

        self.assertTrue(
            {
                "chk_focus_session_status",
                "chk_focus_session_duration",
                "chk_focus_session_remaining",
                "chk_focus_session_version",
                "uq_focus_session_user_request",
            }.issubset(focus_constraints)
        )
        self.assertTrue(
            {
                "chk_focus_session_event_sequence",
                "chk_focus_session_event_actor",
                "chk_focus_session_event_type",
                "uq_focus_session_event_sequence",
                "uq_focus_session_event_action",
            }.issubset(event_constraints)
        )
        active_index = next(
            index for index in FocusSession.__table__.indexes if index.name == "uq_focus_session_running_user"
        )
        self.assertTrue(active_index.unique)
        outbox_fk = next(iter(FocusSession.__table__.c.outbox_message_id.foreign_keys))
        event_fk = next(iter(FocusSessionEvent.__table__.c.session_id.foreign_keys))
        self.assertEqual(outbox_fk.target_fullname, "proactive_message.id")
        self.assertTrue(outbox_fk.deferrable)
        self.assertEqual(event_fk.target_fullname, "focus_session.id")
        self.assertEqual(event_fk.ondelete, "CASCADE")

    def test_bash_models_preserve_user_ownership_and_move_history(self):
        """游戏会话应归属用户，行动应随会话级联删除。"""

        game_user_fk = list(BashGameSession.__table__.c.user_id.foreign_keys)
        move_session_fk = list(BashGameMove.__table__.c.session_id.foreign_keys)
        self.assertEqual(game_user_fk[0].target_fullname, "users.id")
        self.assertEqual(game_user_fk[0].ondelete, "CASCADE")
        self.assertEqual(move_session_fk[0].target_fullname, "bash_game_session.id")
        self.assertEqual(move_session_fk[0].ondelete, "CASCADE")

    def test_relationship_thread_models_preserve_ownership_and_event_history(self):
        """关系线程应归属唯一用户，状态事件应随根线程级联删除。"""

        thread_user_fk = list(RelationshipThread.__table__.c.user_id.foreign_keys)
        event_thread_fk = list(RelationshipThreadEvent.__table__.c.thread_id.foreign_keys)
        self.assertEqual(thread_user_fk[0].target_fullname, "users.id")
        self.assertEqual(thread_user_fk[0].ondelete, "CASCADE")
        self.assertEqual(event_thread_fk[0].target_fullname, "relationship_thread.id")
        self.assertEqual(event_thread_fk[0].ondelete, "CASCADE")

    def test_relationship_thread_constraints_cover_lifecycle_and_idempotency(self):
        """关系线程应约束状态版本，并为来源和客户端动作提供幂等边界。"""

        thread_constraints = {constraint.name for constraint in RelationshipThread.__table__.constraints}
        event_constraints = {constraint.name for constraint in RelationshipThreadEvent.__table__.constraints}
        self.assertTrue(
            {
                "chk_relationship_thread_type",
                "chk_relationship_thread_perspective",
                "chk_relationship_thread_world_layer",
                "chk_relationship_thread_status",
                "chk_relationship_thread_version",
                "uq_relationship_thread_user_source",
            }.issubset(thread_constraints)
        )
        self.assertTrue(
            {
                "chk_relationship_thread_event_sequence",
                "chk_relationship_thread_event_actor",
                "chk_relationship_thread_event_type",
                "uq_relationship_thread_event_sequence",
                "uq_relationship_thread_event_client_action",
            }.issubset(event_constraints)
        )
        self.assertEqual(RelationshipThread.__table__.c.version.server_default.arg, "1")
        self.assertEqual(RelationshipThread.__table__.c.status.server_default.arg, "pending")

    def test_relationship_item_models_perspective_cooldown_and_mutable_stance(self):
        """关系知识应支持事实分层和自然冷却，但不能退化为亲密度打分。"""

        table = RelationshipItem.__table__
        self.assertNotIn("relationship_score", table.c)
        self.assertIsInstance(table.c.confidence.type, Numeric)
        self.assertIsInstance(table.c.can_change.type, Boolean)
        self.assertEqual(table.c.confidence.server_default.arg, "1")
        self.assertEqual(table.c.can_change.server_default.arg, "true")
        constraints = {constraint.name for constraint in table.constraints}
        self.assertTrue(
            {
                "chk_relationship_item_type",
                "chk_relationship_item_perspective",
                "chk_relationship_item_world_layer",
                "chk_relationship_item_status",
                "chk_relationship_item_cooldown",
                "chk_relationship_item_confidence",
                "chk_relationship_item_version",
                "uq_relationship_item_user_key",
            }.issubset(constraints)
        )
        user_fk = next(iter(table.c.user_id.foreign_keys))
        self.assertEqual(user_fk.target_fullname, "users.id")
        self.assertEqual(user_fk.ondelete, "CASCADE")

    def test_relationship_chapter_is_source_idempotent_and_single_current(self):
        """章节必须按来源幂等，并且每个用户同一时刻只能有一个当前章节。"""

        table = RelationshipChapter.__table__
        constraints = {constraint.name for constraint in table.constraints}
        self.assertTrue(
            {
                "chk_relationship_chapter_sequence",
                "chk_relationship_chapter_status",
                "uq_relationship_chapter_user_sequence",
                "uq_relationship_chapter_user_source",
            }.issubset(constraints)
        )
        self.assertFalse(table.c.source_key.nullable)
        current_index = next(
            index for index in table.indexes if index.name == "uq_relationship_chapter_current_user"
        )
        self.assertTrue(current_index.unique)

    def test_continuity_state_models_keep_daily_emotion_and_scene_boundaries(self):
        """连续状态应分别约束自然日、情绪衰减和唯一活动想象场景。"""

        daily_constraints = {constraint.name for constraint in AuraDailyState.__table__.constraints}
        afterglow_constraints = {
            constraint.name for constraint in EmotionalAfterglow.__table__.constraints
        }
        scene_constraints = {constraint.name for constraint in SharedScene.__table__.constraints}
        self.assertTrue(
            {
                "chk_aura_daily_state_energy",
                "chk_aura_daily_state_mood",
                "chk_aura_daily_state_generated_by",
                "uq_aura_daily_state_user_date",
            }.issubset(daily_constraints)
        )
        self.assertTrue(
            {
                "chk_emotional_afterglow_emotion",
                "chk_emotional_afterglow_interaction_mode",
                "chk_emotional_afterglow_intensity",
                "chk_emotional_afterglow_version",
                "uq_emotional_afterglow_user",
            }.issubset(afterglow_constraints)
        )
        self.assertTrue(
            {
                "chk_shared_scene_type",
                "chk_shared_scene_world_layer",
                "chk_shared_scene_status",
                "chk_shared_scene_version",
                "uq_shared_scene_user_source",
            }.issubset(scene_constraints)
        )
        active_index = next(
            index for index in SharedScene.__table__.indexes if index.name == "uq_shared_scene_active_user"
        )
        self.assertTrue(active_index.unique)
        for model in (AuraDailyState, EmotionalAfterglow, SharedScene):
            user_fk = next(iter(model.__table__.c.user_id.foreign_keys))
            self.assertEqual(user_fk.target_fullname, "users.id")
            self.assertEqual(user_fk.ondelete, "CASCADE")

    def test_offline_mind_models_have_lifecycle_and_daily_idempotency(self):
        """思绪种子必须有终态，睡前整理必须按用户自然日唯一。"""

        thought_constraints = {constraint.name for constraint in AuraThoughtSeed.__table__.constraints}
        sleep_constraints = {constraint.name for constraint in AuraSleepCycle.__table__.constraints}
        self.assertTrue(
            {
                "chk_aura_thought_seed_type",
                "chk_aura_thought_seed_status",
                "chk_aura_thought_seed_relevance",
                "uq_aura_thought_seed_user_dedupe",
            }.issubset(thought_constraints)
        )
        self.assertTrue(
            {
                "chk_aura_sleep_cycle_status",
                "chk_aura_sleep_cycle_consolidated_count",
                "uq_aura_sleep_cycle_user_date",
            }.issubset(sleep_constraints)
        )
        for model in (AuraThoughtSeed, AuraSleepCycle):
            user_fk = next(iter(model.__table__.c.user_id.foreign_keys))
            self.assertEqual(user_fk.target_fullname, "users.id")
            self.assertEqual(user_fk.ondelete, "CASCADE")

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
