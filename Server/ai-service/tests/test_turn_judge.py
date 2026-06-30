import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.turn_judge import detect_risk_signal, judge_turn


class TurnJudgeTest(unittest.TestCase):
    @patch("app.core.agent.turn_judge.judge_memory_candidate")
    def test_judge_turn_marks_lonely_support(self, mock_memory_judge):
        mock_memory_judge.return_value = {
            "save": False,
            "memory_scope": "short",
            "title": None,
            "content": None,
            "confidence": 0.0,
            "reason": "test",
            "signals": [],
        }

        result = judge_turn("今天回家突然很孤独，想让你陪我一会儿")

        self.assertEqual(result["emotion"]["user_emotion"], "lonely")
        self.assertEqual(result["response_mode"], "lonely_support")
        self.assertEqual(result["risk_signal"]["level"], "none")
        self.assertEqual(result["relationship_delta"]["label"], "靠近")

    def test_detect_risk_signal_marks_high_self_harm_risk(self):
        result = detect_risk_signal("我真的不想活了")

        self.assertEqual(result["level"], "high")
        self.assertEqual(result["risk_type"], "self_harm")
        self.assertTrue(result["requires_safety_gate"])


if __name__ == "__main__":
    unittest.main()
