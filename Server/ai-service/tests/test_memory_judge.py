import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.judges.memory import (
    fallback_memory_merge,
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

    def test_normalize_long_memory_allows_context_rich_content(self):
        content = (
            "提到跟朋友聚餐时喜欢吃火锅，那次心情似乎不错，还说比一个人随便吃点东西更有仪式感。"
            "这种记忆保留了偏好和场景。"
        )
        candidate = normalize_memory_candidate(
            {
                "save": True,
                "memory_scope": "long",
                "title": "火锅偏好",
                "content": content,
                "confidence": 0.86,
                "reason": "stable_preference_with_context",
                "signals": ["preference", "context"],
            },
            "source",
        )

        self.assertTrue(candidate["save"])
        self.assertEqual(candidate["content"], content)
        self.assertLessEqual(len(candidate["content"]), 220)

    def test_fallback_memory_merge_deduplicates_repeated_contents(self):
        merged = fallback_memory_merge(
            [
                {"title": "火锅偏好", "content": "喜欢和朋友聚餐吃火锅，那次聊起来心情不错。"},
                {"title": "火锅偏好", "content": "喜欢和朋友聚餐吃火锅，那次聊起来心情不错。"},
                {"title": "火锅口味", "content": "吃火锅时不太能吃辣，更偏清汤或番茄锅。"},
            ]
        )

        self.assertEqual(merged["title"], "火锅偏好")
        self.assertEqual(merged["content"].count("喜欢和朋友聚餐吃火锅"), 1)
        self.assertIn("不太能吃辣", merged["content"])

    def test_relationship_candidate_cannot_self_authorize_reminder(self):
        candidate = normalize_memory_candidate(
            {
                "save": True,
                "memory_scope": "mid",
                "title": "面试",
                "content": "明天要面试",
                "relationship_threads": [
                    {
                        "operation": "create",
                        "thread_type": "follow_up",
                        "title": "面试结果",
                        "summary": "明天面试结束后问结果",
                        "follow_up_at": "2026-07-25T10:00:00+08:00",
                        "proactive_allowed": True,
                    }
                ],
            },
            "我明天要面试",
        )

        self.assertEqual(len(candidate["relationship_threads"]), 1)
        self.assertFalse(candidate["relationship_threads"][0]["proactive_allowed"])


if __name__ == "__main__":
    unittest.main()
