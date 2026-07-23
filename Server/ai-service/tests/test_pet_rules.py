from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.core.pet.rules import (
    MIN_CLEANLINESS,
    MIN_SATIETY,
    PetState,
    apply_pet_action,
    growth_stage_for,
    natural_pet_status,
    settle_pet_state,
)


class PetRulesTest(unittest.TestCase):
    """验证宠物惰性结算、温和下限、成长和照顾动作。"""

    def build_state(self, now: datetime, **overrides) -> PetState:
        """构造默认宠物状态，并允许测试覆盖指定字段。"""

        values = {
            "satiety": 80,
            "energy": 60,
            "cleanliness": 80,
            "mood": "calm",
            "current_activity": "idle",
            "growth_stage": "baby",
            "adopted_at": now,
            "mood_until_at": None,
            "activity_ends_at": None,
            "last_settled_at": now,
        }
        values.update(overrides)
        return PetState(**values)

    def test_less_than_one_quantum_preserves_numeric_remainder(self) -> None:
        """未满三小时不应消耗时间余量或改变照顾数值。"""

        now = datetime(2026, 7, 23, 8, tzinfo=UTC)
        state = self.build_state(now)
        result = settle_pet_state(state, now + timedelta(hours=2, minutes=59))
        self.assertFalse(result.changed)
        self.assertEqual(result.state.last_settled_at, now)

    def test_full_quantum_applies_gentle_decay_and_recovery(self) -> None:
        """每满三小时应按固定规则下降饱腹/清洁并恢复精力。"""

        now = datetime(2026, 7, 23, 8, tzinfo=UTC)
        result = settle_pet_state(self.build_state(now), now + timedelta(hours=3))
        self.assertEqual(result.state.satiety, 77)
        self.assertEqual(result.state.cleanliness, 79)
        self.assertEqual(result.state.energy, 62)
        self.assertEqual(result.state.last_settled_at, now + timedelta(hours=3))

    def test_long_absence_stops_at_safe_non_punitive_floors(self) -> None:
        """长期离线后饱腹和清洁仍停在安全下限，不产生死亡或疾病状态。"""

        now = datetime(2026, 7, 23, 8, tzinfo=UTC)
        result = settle_pet_state(self.build_state(now), now + timedelta(days=365))
        self.assertEqual(result.state.satiety, MIN_SATIETY)
        self.assertEqual(result.state.cleanliness, MIN_CLEANLINESS)
        self.assertEqual(result.state.mood, "calm")
        self.assertNotIn(result.state.current_activity, {"sick", "dead", "missing"})

    def test_expired_mood_and_activity_return_to_calm_idle(self) -> None:
        """短暂动作结束后只回到平静和空闲，不变成负面心情。"""

        now = datetime(2026, 7, 23, 8, tzinfo=UTC)
        state = self.build_state(
            now,
            mood="playful",
            current_activity="playing",
            mood_until_at=now + timedelta(minutes=30),
            activity_ends_at=now + timedelta(minutes=20),
        )
        result = settle_pet_state(state, now + timedelta(hours=1))
        self.assertEqual(result.state.mood, "calm")
        self.assertEqual(result.state.current_activity, "idle")

    def test_growth_stages_follow_adoption_age_without_death_stage(self) -> None:
        """成长只包含 baby、young、adult 三个自然阶段。"""

        adopted = datetime(2026, 1, 1, tzinfo=UTC)
        self.assertEqual(growth_stage_for(adopted, adopted + timedelta(days=13)), "baby")
        self.assertEqual(growth_stage_for(adopted, adopted + timedelta(days=14)), "young")
        self.assertEqual(growth_stage_for(adopted, adopted + timedelta(days=60)), "adult")
        self.assertEqual(growth_stage_for(adopted, adopted + timedelta(days=3650)), "adult")

    def test_all_actions_keep_scores_in_safe_ranges(self) -> None:
        """六种动作都应产生合法状态，玩耍也不会把精力降到危险值。"""

        now = datetime(2026, 7, 23, 8, tzinfo=UTC)
        for action in ("feed", "play", "groom", "bathe", "pet", "sleep"):
            with self.subTest(action=action):
                result = apply_pet_action(self.build_state(now), action, now)
                self.assertGreaterEqual(result.state.satiety, MIN_SATIETY)
                self.assertGreaterEqual(result.state.cleanliness, MIN_CLEANLINESS)
                self.assertGreaterEqual(result.state.energy, 10)
                self.assertLessEqual(result.state.energy, 100)

    def test_natural_status_hides_scores(self) -> None:
        """自然状态只返回文字标签，不暴露关系式打分。"""

        now = datetime(2026, 7, 23, 8, tzinfo=UTC)
        status = natural_pet_status(self.build_state(now))
        self.assertTrue(all(isinstance(value, str) for value in status.values()))
        self.assertNotIn("亲密度", "".join(status.values()))


if __name__ == "__main__":
    unittest.main()
