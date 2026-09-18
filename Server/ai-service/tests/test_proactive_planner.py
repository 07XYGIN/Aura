from datetime import UTC, datetime, timedelta
import unittest

from app.core.proactive.planner import plan_relationship_contact


class ProactivePlannerTests(unittest.TestCase):
    def test_plans_grounded_thread_follow_up(self) -> None:
        now = datetime(2026, 9, 18, 8, tzinfo=UTC)
        intent = plan_relationship_contact(
            {
                "desire_for_contact": "high",
                "missing_user": "clear",
                "last_user_seen_at": now - timedelta(hours=8),
                "last_proactive_at": None,
                "unresolved_feeling": False,
            },
            {"current_expectation": "等接口结果"},
            now=now,
            daily_contact_count=0,
            deep_night=False,
            thread_title="接口故障",
            thread_id="thread-1",
        )

        self.assertIsNotNone(intent)
        self.assertIn("接口故障", intent.content)
        self.assertEqual(intent.source, "relationship_thread")

    def test_respects_cooldown(self) -> None:
        now = datetime(2026, 9, 18, 8, tzinfo=UTC)
        intent = plan_relationship_contact(
            {
                "desire_for_contact": "high",
                "missing_user": "clear",
                "last_user_seen_at": now - timedelta(hours=8),
                "last_proactive_at": now - timedelta(hours=2),
            },
            {},
            now=now,
            daily_contact_count=0,
            deep_night=False,
        )

        self.assertIsNone(intent)


if __name__ == "__main__":
    unittest.main()

