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
    @patch("app.core.agent.turn_judge.judge_emotion_state")
    def test_judge_turn_marks_lonely_support(self, mock_emotion_judge, mock_memory_judge):
        mock_emotion_judge.return_value = {
            "user_emotion": "lonely",
            "aura_mood": "tender",
            "valence": -0.7,
            "arousal": 0.35,
            "intensity": 0.8,
            "affection": 1.0,
            "support_needed": True,
            "matched_keywords": ["孤独", "陪我"],
            "response_guidance": "test",
            "is_current_experience": True,
            "emotion_confidence": 0.9,
        }
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

    @patch("app.core.agent.turn_judge.judge_memory_candidate")
    @patch("app.core.agent.turn_judge.judge_emotion_state")
    def test_judge_turn_keeps_retrospective_tired_statement_natural(self, mock_emotion_judge, mock_memory_judge):
        mock_emotion_judge.return_value = {
            "user_emotion": "tired",
            "aura_mood": "warm",
            "valence": -0.4,
            "arousal": 0.2,
            "intensity": 0.25,
            "affection": 0.8,
            "support_needed": False,
            "matched_keywords": ["累"],
            "response_guidance": "这是回忆或习惯描述，不要过度安抚。",
            "is_current_experience": False,
            "emotion_confidence": 0.88,
        }
        mock_memory_judge.return_value = {
            "save": False,
            "memory_scope": "short",
            "title": None,
            "content": None,
            "confidence": 0.0,
            "reason": "test",
            "signals": [],
        }

        result = judge_turn("代码写累了就起来走走")

        self.assertEqual(result["response_mode"], "natural_chat")
        self.assertFalse(result["emotion"]["support_needed"])
        self.assertFalse(result["emotion"]["is_current_experience"])

    def test_detect_risk_signal_marks_high_self_harm_risk(self):
        result = detect_risk_signal("我真的不想活了")

        self.assertEqual(result["level"], "high")
        self.assertEqual(result["risk_type"], "self_harm")
        self.assertTrue(result["requires_safety_gate"])


if __name__ == "__main__":
    unittest.main()
