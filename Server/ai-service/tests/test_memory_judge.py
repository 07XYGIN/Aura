import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.memory_judge import (
    normalize_memory_candidate,
    normalize_memory_dedup_decision,
    parse_json_object,
)


class MemoryJudgeTest(unittest.TestCase):
    def test_parse_json_object_extracts_object_from_model_text(self):
        parsed = parse_json_object('```json\n{"save": true, "memory_scope": "long"}\n```')

        self.assertEqual(parsed, {"save": True, "memory_scope": "long"})

    def test_normalize_short_memory_never_saves(self):
        candidate = normalize_memory_candidate(
            {
                "save": True,
                "memory_scope": "short",
                "title": "chat",
                "content": "hello",
                "confidence": 0.9,
                "reason": "small_talk",
                "signals": ["greeting"],
            },
            "hello",
        )

        self.assertFalse(candidate["save"])
        self.assertEqual(candidate["memory_scope"], "short")

    def test_normalize_long_memory_fills_missing_content(self):
        candidate = normalize_memory_candidate(
            {
                "save": True,
                "memory_scope": "long",
                "confidence": "0.8",
                "signals": ["preference"],
            },
            "I prefer quiet cafes when working.",
        )

        self.assertTrue(candidate["save"])
        self.assertEqual(candidate["content"], "I prefer quiet cafes when working.")
        self.assertEqual(candidate["confidence"], 0.8)

    def test_normalize_memory_dedup_decision_rejects_unknown_decision(self):
        decision = normalize_memory_dedup_decision(
            {
                "decision": "merge",
                "confidence": 1.4,
                "reason": "too much",
            }
        )

        self.assertEqual(decision["decision"], "unrelated")
        self.assertEqual(decision["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
