from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from app.core.continuity.knowledge import (
    MAX_CAPTURE_SOURCE_IDS,
    RelationshipKnowledgeServiceError,
    apply_item_candidate,
    build_chapter_source_key,
    capture_item_candidate,
    capture_relationship_knowledge_sync,
    close_current_chapter,
    mark_item_used,
    next_chapter_sequence,
    parse_http_uuid,
    resolve_usage_target_ids,
    source_already_applied,
    validate_chapter_candidate,
    validate_item_candidate,
    validate_item_candidates,
    with_capture_source,
)


class RelationshipKnowledgeDomainTest(unittest.TestCase):
    """验证不依赖真实 PostgreSQL 的关系知识校验、版本与幂等规则。"""

    def setUp(self) -> None:
        """为所有状态变化测试固定 UTC 时间，避免时区和微秒造成噪声。"""

        self.now = datetime(2026, 7, 23, 8, 30, tzinfo=UTC)

    def build_upsert(self, **overrides: object) -> dict[str, object]:
        """构造一条包含完整快照、可直接新建物件的 upsert 候选。"""

        candidate: dict[str, object] = {
            "operation": "upsert",
            "item_type": "action_style",
            "perspective": "aura",
            "world_layer": "shared_history",
            "item_key": "style:action-description",
            "title": "动作描写偶尔使用",
            "content": "喜欢偶尔使用动作描写，但不要每句话都模板化添加。",
            "usage_condition": "亲密互动且动作能补充语义时",
            "confidence": 0.86,
            "can_change": True,
            "cooldown_days": 3,
            "metadata": {"formed_from": ["turn-1"]},
        }
        candidate.update(overrides)
        return candidate

    def build_item(self, **overrides: object) -> SimpleNamespace:
        """构造 apply/mark 所需字段齐全的轻量 ORM 替身。"""

        item = SimpleNamespace(
            id=uuid4(),
            item_type="action_style",
            perspective="aura",
            world_layer="shared_history",
            item_key="style:action-description",
            title="动作描写偶尔使用",
            content="旧内容",
            usage_condition=None,
            confidence=0.8,
            can_change=True,
            status="active",
            cooldown_days=7,
            last_used_at=None,
            use_count=0,
            source_message_id="message-old",
            version=2,
            metadata_json={"capture_source_ids": ["message-old"]},
            updated_at=self.now,
        )
        for key, value in overrides.items():
            setattr(item, key, value)
        return item

    def test_item_candidate_requires_valid_complete_upsert_snapshot(self) -> None:
        valid = validate_item_candidate(self.build_upsert())

        self.assertIsNotNone(valid)
        self.assertEqual(valid["confidence"], 0.86)
        self.assertEqual(valid["cooldown_days"], 3)
        self.assertIsNone(validate_item_candidate(self.build_upsert(item_type="unknown")))
        self.assertIsNone(validate_item_candidate(self.build_upsert(content="   ")))
        self.assertIsNone(validate_item_candidate(self.build_upsert(confidence=float("nan"))))

    def test_update_requires_target_and_actual_mutable_field(self) -> None:
        target_id = uuid4()

        self.assertIsNone(
            validate_item_candidate({"operation": "update", "target_id": str(target_id)})
        )
        candidate = validate_item_candidate(
            {
                "operation": "update",
                "target_id": str(target_id),
                "content": "以后先正常接话，不要立刻给建议。",
            }
        )

        self.assertEqual(candidate["target_id"], target_id)
        self.assertEqual(candidate["content"], "以后先正常接话，不要立刻给建议。")

    def test_candidates_keep_only_first_operation_for_same_item(self) -> None:
        candidates = validate_item_candidates(
            [
                self.build_upsert(content="第一版"),
                self.build_upsert(content="互相冲突的第二版"),
                {"operation": "deactivate", "item_key": "style:action-description"},
            ]
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["content"], "第一版")

    def test_apply_upsert_changes_semantics_once_and_preserves_source_idempotency(self) -> None:
        item = self.build_item()
        candidate = validate_item_candidate(self.build_upsert(content="新的稳定立场"))

        changed = apply_item_candidate(
            item,
            candidate,
            source_message_id="message-new",
            source_turn_id="turn-new",
            occurred_at=self.now,
        )

        self.assertTrue(changed)
        self.assertEqual(item.content, "新的稳定立场")
        self.assertEqual(item.version, 3)
        self.assertEqual(item.source_message_id, "message-new")
        self.assertTrue(source_already_applied(item, "message-new"))

        replayed = apply_item_candidate(
            item,
            candidate,
            source_message_id="message-new",
            source_turn_id="turn-new",
            occurred_at=self.now,
        )
        self.assertFalse(replayed)
        self.assertEqual(item.version, 3)

    def test_semantically_equal_new_upsert_records_source_without_bumping_version(self) -> None:
        candidate = validate_item_candidate(self.build_upsert())
        item = self.build_item(
            content=candidate["content"],
            usage_condition=candidate["usage_condition"],
            confidence=candidate["confidence"],
            cooldown_days=candidate["cooldown_days"],
            metadata_json={"formed_from": ["turn-1"]},
        )

        changed = apply_item_candidate(
            item,
            candidate,
            source_message_id="message-same-semantics",
            source_turn_id="turn-2",
            occurred_at=self.now,
        )

        self.assertFalse(changed)
        self.assertEqual(item.version, 2)
        self.assertTrue(source_already_applied(item, "message-same-semantics"))

    def test_deactivate_is_versioned_and_replay_safe(self) -> None:
        item = self.build_item()
        candidate = validate_item_candidate(
            {"operation": "deactivate", "item_key": item.item_key}
        )

        self.assertTrue(
            apply_item_candidate(
                item,
                candidate,
                source_message_id="message-stop",
                source_turn_id=None,
                occurred_at=self.now,
            )
        )
        self.assertEqual(item.status, "inactive")
        self.assertEqual(item.version, 3)
        self.assertFalse(
            apply_item_candidate(
                item,
                candidate,
                source_message_id="message-stop",
                source_turn_id=None,
                occurred_at=self.now,
            )
        )

    def test_upsert_with_stale_explicit_target_does_not_create_duplicate(self) -> None:
        """携带 target_id 的更新不能在目标消失后按新 item_key 静默新建。"""

        session = Mock()
        session.execute.return_value.scalar_one_or_none.return_value = None
        candidate = validate_item_candidate(
            self.build_upsert(target_id=str(uuid4()), title="改名后的标题")
        )

        changed = capture_item_candidate(
            session,
            uuid4(),
            candidate,
            source_message_id="message-stale-target",
            source_turn_id="turn-stale-target",
            occurred_at=self.now,
        )

        self.assertEqual(changed, 0)
        session.add.assert_not_called()

    def test_capture_source_history_is_bounded_and_keeps_latest_message(self) -> None:
        metadata: dict[str, object] = {}
        for index in range(MAX_CAPTURE_SOURCE_IDS + 5):
            metadata = with_capture_source(
                metadata,
                source_message_id=f"message-{index}",
                source_turn_id=None,
            )

        history = metadata["capture_source_ids"]
        self.assertEqual(len(history), MAX_CAPTURE_SOURCE_IDS)
        self.assertNotIn("message-0", history)
        self.assertEqual(history[-1], f"message-{MAX_CAPTURE_SOURCE_IDS + 4}")

    def test_chapter_source_key_is_stable_and_candidate_can_derive_it(self) -> None:
        user_id = uuid4()
        first = build_chapter_source_key(user_id, "message-1")
        second = build_chapter_source_key(str(user_id), "message-1")

        self.assertEqual(first, second)
        self.assertNotEqual(first, build_chapter_source_key(user_id, "message-2"))
        candidate = validate_chapter_candidate(
            {"title": "一起设计 Aura", "summary": "从调参数走到共同设计连续性。"},
            user_id=user_id,
            source_message_id="message-1",
        )
        self.assertEqual(candidate["source_key"], first)

    def test_closing_chapter_and_next_sequence_are_monotonic(self) -> None:
        chapter = SimpleNamespace(status="current", ended_at=None, updated_at=None)

        close_current_chapter(chapter, self.now)

        self.assertEqual(chapter.status, "closed")
        self.assertEqual(chapter.ended_at, self.now)
        self.assertEqual(next_chapter_sequence(None), 1)
        self.assertEqual(next_chapter_sequence(7), 8)
        self.assertEqual(next_chapter_sequence("invalid"), 1)

    def test_usage_refs_cannot_escape_loaded_context_and_are_deduplicated(self) -> None:
        item_one = uuid4()
        item_two = uuid4()
        forged = uuid4()
        context = [
            {"ref": "K1", "id": str(item_one)},
            {"ref": "K2", "id": str(item_two)},
        ]

        resolved = resolve_usage_target_ids(
            context,
            ["K1", {"itemRef": "K2"}, {"item_ref": "K1"}, str(forged), "K99"],
        )

        self.assertEqual(resolved, [item_one, item_two])
        self.assertNotIn(forged, resolved)

    def test_mark_item_used_is_idempotent_per_turn(self) -> None:
        item = self.build_item()

        first = mark_item_used(item, used_at=self.now, source_turn_id="reply-turn-1")
        replay = mark_item_used(item, used_at=self.now, source_turn_id="reply-turn-1")

        self.assertTrue(first)
        self.assertFalse(replay)
        self.assertEqual(item.use_count, 1)
        self.assertEqual(item.last_used_at, self.now)

    def test_chat_capture_swallows_database_failure(self) -> None:
        with patch("app.core.continuity.knowledge.SyncSessionLocal") as session_factory:
            session_factory.begin.side_effect = RuntimeError("database unavailable")
            with self.assertLogs(level="ERROR") as captured_logs:
                changed = capture_relationship_knowledge_sync(
                    str(uuid4()),
                    [self.build_upsert()],
                    None,
                    "message-db-failure",
                    "turn-db-failure",
                    now=self.now,
                )

        self.assertEqual(changed, 0)
        self.assertIn("聊天继续", "\n".join(captured_logs.output))

    def test_http_uuid_error_stays_separate_from_chat_degradation(self) -> None:
        with self.assertRaises(RelationshipKnowledgeServiceError) as raised:
            parse_http_uuid("not-a-uuid", "关系物件 ID")

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("关系物件 ID", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
