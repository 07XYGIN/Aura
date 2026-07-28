from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.conversation_regression import evaluate_conversation_reply


class ConversationRegressionTest(unittest.TestCase):
    """守住 Aura 已确认的日常聊天边界。"""

    def test_curated_cases_stay_within_the_preferred_style(self) -> None:
        fixture = Path(__file__).with_name("fixtures") / "conversation_regression_cases.json"
        cases = json.loads(fixture.read_text(encoding="utf-8"))

        for case in cases:
            with self.subTest(case=case["name"]):
                result = evaluate_conversation_reply(case["user"], case["reply"])
                self.assertTrue(result.passed, result.violations)

    def test_rejects_invented_daily_routine_for_a_simple_greeting(self) -> None:
        result = evaluate_conversation_reply(
            "早呀",
            "早。今天起得还挺早，不像你周末的风格。我在工作室靠窗改图标。",
        )

        self.assertFalse(result.passed)
        self.assertIn("简短寒暄中编造 Aura 日常或评价用户习惯", result.violations)

    def test_rejects_automatic_correction_of_boredom(self) -> None:
        result = evaluate_conversation_reply(
            "不知道呢，今天也是无聊的一天",
            "那你先别急着定无聊，先吃点东西，把早上这口气喘匀。",
        )

        self.assertFalse(result.passed)
        self.assertIn("无聊表达被自动纠正或安排任务", result.violations)


if __name__ == "__main__":
    unittest.main()
