from __future__ import annotations

import unittest
from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.core.agent.tools import proactive


class ProactiveToolTest(unittest.TestCase):
    def test_daily_greeting_plan_uses_requested_windows(self):
        now = datetime(2026, 7, 8, 5, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        plan = proactive.build_daily_greeting_plan(
            user_id="user-1",
            timezone="Asia/Shanghai",
            now=now,
            target_date=date(2026, 7, 8),
        )

        morning_at = datetime.fromisoformat(plan["morning"]["scheduled_at"])
        evening_at = datetime.fromisoformat(plan["evening"]["scheduled_at"])
        self.assertEqual(plan["morning"]["window"], "06:00:00-08:00:00")
        self.assertEqual(plan["evening"]["window"], "20:00:00-23:00:00")
        self.assertGreaterEqual(morning_at.timetz().replace(tzinfo=None), time(6, 0))
        self.assertLessEqual(morning_at.timetz().replace(tzinfo=None), time(8, 0))
        self.assertGreaterEqual(evening_at.timetz().replace(tzinfo=None), time(20, 0))
        self.assertLessEqual(evening_at.timetz().replace(tzinfo=None), time(23, 0))
        self.assertIn("天气", plan["morning"]["reply_spec"])
        self.assertIn("晚安", plan["evening"]["reply_spec"])

    def test_daily_greeting_plan_is_stable_for_same_user_and_date(self):
        now = datetime(2026, 7, 8, 5, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        first = proactive.build_daily_greeting_plan(
            user_id="user-1",
            timezone="Asia/Shanghai",
            now=now,
            target_date=date(2026, 7, 8),
        )
        second = proactive.build_daily_greeting_plan(
            user_id="user-1",
            timezone="Asia/Shanghai",
            now=now,
            target_date=date(2026, 7, 8),
        )

        self.assertEqual(first["morning"]["scheduled_at"], second["morning"]["scheduled_at"])
        self.assertEqual(first["evening"]["scheduled_at"], second["evening"]["scheduled_at"])

    def test_llm_draft_falls_back_to_safe_morning_template(self):
        fake_llm = SimpleNamespace(invoke=unittest.mock.Mock(side_effect=RuntimeError("offline")))
        with patch("app.core.agent.tools.proactive.structured_reply_llm", fake_llm):
            draft = proactive.draft_proactive_message_with_llm(
                proactive.MORNING_TRIGGER_TYPE,
                weather_context={
                    "status": "1",
                    "city": "上海",
                    "weather": "小雨",
                    "temperature": "24",
                },
            )

        self.assertEqual(draft["source"], "fallback_template")
        self.assertIn("早上好", draft["content"])
        self.assertIn("上海", draft["content"])


if __name__ == "__main__":
    unittest.main()
