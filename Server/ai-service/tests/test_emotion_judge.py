import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.judges.emotion import (
    infer_interaction_mode,
    normalize_emotion_judgement,
    suppress_retrospective_false_positive,
)


class EmotionJudgeTest(unittest.TestCase):
    def test_emotion_output_does_not_include_handwritten_scores(self):
        result = normalize_emotion_judgement(
            {
                "emotional_state": "positive",
                "is_current_experience": True,
                "interaction_mode": "natural",
                "interaction_target": "external",
                "confidence": 0.9,
                "reason": "用户在分享开心的事",
            },
            {"matched_keywords": ["开心"]},
            "今天项目终于跑通了，挺开心",
        )

        self.assertNotIn("valence", result)
        self.assertNotIn("arousal", result)
        self.assertNotIn("affection", result)
        self.assertNotIn("intensity", result)

    def test_external_frustration_is_not_relationship_repair(self):
        self.assertEqual(infer_interaction_mode("今天工作真的好烦"), "natural")
        self.assertEqual(infer_interaction_mode("我讨厌这种下雨天"), "natural")

    def test_direct_complaint_to_aura_can_enter_repair(self):
        self.assertEqual(infer_interaction_mode("你刚才那句话让我很难受"), "repair")

    def test_retrospective_negative_judgement_does_not_need_support(self):
        fallback = {
            "user_emotion": "tired",
            "aura_mood": "quiet",
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
                "interaction_mode": "natural",
                "interaction_target": "external",
            },
            fallback,
            "代码写累了就起来走走",
        )

        self.assertFalse(result["support_needed"])
        self.assertFalse(result["is_current_experience"])
        self.assertEqual(result["aura_mood"], "natural")

    def test_current_low_judgement_needs_support(self):
        fallback = {
            "user_emotion": "distressed",
            "aura_mood": "steady",
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
                "interaction_mode": "natural",
                "interaction_target": "self",
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
            "aura_mood": "quiet",
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
