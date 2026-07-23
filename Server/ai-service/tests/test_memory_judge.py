import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.judges.memory import (
    fallback_memory_merge,
    judge_memory_candidate,
    memory_candidate,
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

    def test_relationship_item_accepts_evidence_from_recent_real_dialogue(self):
        candidate = normalize_memory_candidate(
            {
                "save": False,
                "memory_scope": "short",
                "relationship_items": [
                    {
                        "operation": "upsert",
                        "item_type": "aura_stance",
                        "perspective": "aura",
                        "world_layer": "shared_history",
                        "title": "动作描写不要模板化",
                        "content": "Aura 喜欢偶尔使用动作描写，但反对每句话都套模板。",
                        "confidence": 0.9,
                        "can_change": True,
                        "evidence": "偶尔用一下挺有感觉的",
                    }
                ],
            },
            "我觉得可以把这个想法记下来",
            recent_context="Aura：偶尔用一下挺有感觉的，但每句话都写就不是我了。",
        )

        self.assertEqual(len(candidate["relationship_items"]), 1)
        item = candidate["relationship_items"][0]
        self.assertEqual(item["item_type"], "aura_stance")
        self.assertEqual(item["perspective"], "aura")
        self.assertEqual(item["evidence"], "偶尔用一下挺有感觉的")

    def test_relationship_item_rejects_model_invented_evidence(self):
        candidate = normalize_memory_candidate(
            {
                "save": False,
                "memory_scope": "short",
                "relationship_items": [
                    {
                        "operation": "upsert",
                        "item_type": "running_joke",
                        "perspective": "shared",
                        "world_layer": "shared_history",
                        "title": "并不存在的玩笑",
                        "content": "模型自行补写的共同玩笑。",
                        "confidence": 0.98,
                        "evidence": "我们每次都这样开玩笑",
                    }
                ],
            },
            "今天继续改后端吧",
            recent_context="昨天讨论了关系线程。",
        )

        self.assertEqual(candidate["relationship_items"], [])

    def test_relationship_chapter_requires_real_high_importance_stage_change(self):
        evidence = "我们决定以后不再用亲密度分数衡量关系"
        candidate = normalize_memory_candidate(
            {
                "save": True,
                "memory_scope": "long",
                "relationship_chapter": {
                    "create": True,
                    "title": "从打分走向共同设计",
                    "summary": "小乔和 Aura 共同确定，不再用分数衡量关系，而用真实经历延续关系。",
                    "world_layer": "shared_history",
                    "importance": 0.94,
                    "confidence": 0.9,
                    "evidence": evidence,
                },
            },
            evidence,
        )

        self.assertIsNotNone(candidate["relationship_chapter"])
        self.assertEqual(candidate["relationship_chapter"]["world_layer"], "shared_history")

    def test_relationship_chapter_rejects_imagined_or_ordinary_event(self):
        candidate = normalize_memory_candidate(
            {
                "save": False,
                "memory_scope": "short",
                "relationship_chapter": {
                    "create": True,
                    "title": "一次想象中的旅行",
                    "summary": "双方假想一起旅行。",
                    "world_layer": "imagined",
                    "importance": 1.0,
                    "confidence": 1.0,
                    "evidence": "假如我们一起去旅行",
                },
            },
            "假如我们一起去旅行",
        )

        self.assertIsNone(candidate["relationship_chapter"])

    def test_judge_adds_deterministic_item_when_model_returns_no_item(self):
        response = SimpleNamespace(
            content=(
                '{"save":false,"memory_scope":"short","confidence":0,'
                '"reason":"style feedback","signals":[],"relationship_threads":[],'
                '"relationship_items":[],"relationship_chapter":null}'
            )
        )
        with patch(
            "app.core.agent.judges.memory.memory_judge_llm",
            SimpleNamespace(invoke=Mock(return_value=response)),
        ):
            candidate = judge_memory_candidate("你这句话太客服了")

        self.assertEqual(len(candidate["relationship_items"]), 1)
        self.assertEqual(candidate["relationship_items"][0]["item_type"], "action_style")
        self.assertIsNone(candidate["relationship_chapter"])

    def test_judge_failure_keeps_deterministic_item_fallback(self):
        with patch(
            "app.core.agent.judges.memory.memory_judge_llm",
            SimpleNamespace(invoke=Mock(side_effect=RuntimeError("offline"))),
        ):
            candidate = judge_memory_candidate("别每次都安慰我")

        self.assertFalse(candidate["save"])
        self.assertEqual(candidate["relationship_items"][0]["item_type"], "boundary")
        self.assertIsNone(candidate["relationship_chapter"])

    def test_memory_candidate_old_signature_gets_new_empty_fields(self):
        candidate = memory_candidate(False, "short", None, None, 0.0, "test", [])

        self.assertEqual(candidate["relationship_threads"], [])
        self.assertEqual(candidate["relationship_items"], [])
        self.assertIsNone(candidate["relationship_chapter"])

    def test_vector_memory_preserves_imagined_world_layer(self):
        candidate = normalize_memory_candidate(
            {
                "save": True,
                "memory_scope": "long",
                "title": "想象中的旅行",
                "content": "双方想象以后一起去海边。",
                "perspective": "shared",
                "world_layer": "imagined",
            },
            "假如以后一起去海边就好了",
        )

        self.assertTrue(candidate["save"])
        self.assertEqual(candidate["perspective"], "shared")
        self.assertEqual(candidate["world_layer"], "imagined")

    def test_unknown_vector_memory_world_layer_disables_save(self):
        candidate = normalize_memory_candidate(
            {
                "save": True,
                "memory_scope": "long",
                "title": "不可信分类",
                "content": "不能把未知层静默当成现实。",
                "perspective": "shared",
                "world_layer": "roleplay_reality",
            },
            "这是一个假设",
        )

        self.assertFalse(candidate["save"])
        self.assertEqual(candidate["world_layer"], "reality")


if __name__ == "__main__":
    unittest.main()
