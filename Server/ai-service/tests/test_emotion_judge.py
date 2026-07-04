import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.emotion_judge import (
    normalize_emotion_judgement,
    suppress_retrospective_false_positive,
)


class EmotionJudgeTest(unittest.TestCase):
    def test_retrospective_negative_judgement_does_not_need_support(self):
        fallback = {
            "user_emotion": "tired",
            "aura_mood": "soothing",
            "valence": -0.4,
            "arousal": 0.2,
            "intensity": 0.6,
            "affection": 0.85,
            "support_needed": True,
            "matched_keywords": ["累"],
            "response_guidance": "fallback",
        }

        result = normalize_emotion_judgement(
            {
                "emotional_state": "tired",
                "is_current_experience": False,
                "confidence": 0.9,
                "reason": "用户在描述一种习惯，不是当下求安抚",
            },
            fallback,
            "代码写累了就起来走走",
        )

        self.assertFalse(result["support_needed"])
        self.assertFalse(result["is_current_experience"])
        self.assertEqual(result["aura_mood"], "warm")

    def test_current_low_judgement_needs_support(self):
        fallback = {
            "user_emotion": "distressed",
            "aura_mood": "protective",
            "valence": -0.8,
            "arousal": 0.7,
            "intensity": 0.7,
            "affection": 0.9,
            "support_needed": True,
            "matched_keywords": ["撑不下去"],
            "response_guidance": "fallback",
        }

        result = normalize_emotion_judgement(
            {
                "emotional_state": "low",
                "is_current_experience": True,
                "confidence": 0.92,
                "reason": "用户正在表达当下低落",
            },
            fallback,
            "今天真的很累，感觉撑不下去了",
        )

        self.assertTrue(result["support_needed"])
        self.assertTrue(result["is_current_experience"])
        self.assertEqual(result["user_emotion"], "distressed")

    def test_keyword_fallback_suppresses_habitual_tired_statement(self):
        fallback = {
            "user_emotion": "tired",
            "aura_mood": "soothing",
            "valence": -0.4,
            "arousal": 0.2,
            "intensity": 0.7,
            "affection": 0.85,
            "support_needed": True,
            "matched_keywords": ["累"],
            "response_guidance": "fallback",
        }

        result = suppress_retrospective_false_positive(fallback, "代码写累了就起来走走")

        self.assertFalse(result["support_needed"])
        self.assertFalse(result["is_current_experience"])
        self.assertEqual(result["emotion_source"], "keyword_context_suppression")


if __name__ == "__main__":
    unittest.main()
