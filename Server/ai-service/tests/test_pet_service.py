from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.core.pet.service import (
    PetServiceError,
    apply_state_to_model,
    ensure_pet_event_replay,
    ensure_pet_version,
    pet_state_from_model,
    settle_pet_model,
)


class PetServiceDomainTest(unittest.TestCase):
    """验证宠物事务服务中不依赖数据库 I/O 的状态步骤。"""

    def build_pet(self, now: datetime):
        """构造包含服务转换函数所需字段的轻量宠物对象。"""

        return SimpleNamespace(
            id=uuid4(),
            name="团子",
            satiety=80,
            energy=60,
            cleanliness=80,
            mood="calm",
            current_activity="idle",
            growth_stage="baby",
            adopted_at=now,
            mood_until_at=None,
            activity_ends_at=None,
            last_settled_at=now,
            version=1,
        )

    def test_model_state_round_trip_preserves_rule_fields(self) -> None:
        """ORM 到不可变状态再写回时应保持规则字段一致。"""

        now = datetime(2026, 7, 23, 8, tzinfo=UTC)
        pet = self.build_pet(now)
        state = pet_state_from_model(pet)
        updated = state.__class__(**{**state.__dict__, "satiety": 90, "mood": "content"})
        apply_state_to_model(pet, updated)
        self.assertEqual(pet.satiety, 90)
        self.assertEqual(pet.mood, "content")

    def test_settle_model_creates_growth_event_once(self) -> None:
        """跨过成长边界时应更新阶段并构造一条系统里程碑事件。"""

        adopted = datetime(2026, 7, 1, tzinfo=UTC)
        pet = self.build_pet(adopted)
        changed, events = settle_pet_model(pet, adopted + timedelta(days=14))
        self.assertTrue(changed)
        self.assertEqual(pet.growth_stage, "young")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "growth")

        changed_again, events_again = settle_pet_model(pet, adopted + timedelta(days=14))
        self.assertFalse(changed_again)
        self.assertEqual(events_again, [])

    def test_expected_version_rejects_stale_client(self) -> None:
        """旧版本必须在状态修改前转换为 409 冲突。"""

        pet = self.build_pet(datetime(2026, 7, 23, tzinfo=UTC))
        with self.assertRaises(PetServiceError) as raised:
            ensure_pet_version(pet, expected_version=2)
        self.assertEqual(raised.exception.status_code, 409)

    def test_client_action_id_cannot_replay_a_different_operation(self) -> None:
        """跨动作复用幂等 ID 必须返回 409，不能伪装成当前动作成功。"""

        original_event = SimpleNamespace(event_type="action", action="feed", metadata_json={})
        ensure_pet_event_replay(
            original_event,
            expected_event_type="action",
            expected_action="feed",
        )
        with self.assertRaises(PetServiceError) as raised:
            ensure_pet_event_replay(
                original_event,
                expected_event_type="rename",
                expected_action="rename",
            )
        self.assertEqual(raised.exception.status_code, 409)

    def test_client_action_id_cannot_replay_different_payload(self) -> None:
        """同类操作使用相同 ID 但修改业务参数时也必须返回 409。"""

        rename_event = SimpleNamespace(
            event_type="rename",
            action="rename",
            metadata_json={"new_name": "团子"},
        )
        with self.assertRaises(PetServiceError) as raised:
            ensure_pet_event_replay(
                rename_event,
                expected_event_type="rename",
                expected_action="rename",
                expected_payload={"new_name": "糯米"},
            )
        self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
