import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.judges.impulse import (
    collect_impulse_candidates,
    judge_aura_impulse,
    resolve_impulse_candidates,
)


class AuraImpulseTest(unittest.TestCase):
    def test_after_work_message_can_follow_up_real_relationship_thread(self):
        result = judge_aura_impulse(
            "我下班了",
            [],
            {"risk_signal": {"requires_safety_gate": False}, "emotion": {}},
            {
                "items": [
                    {
                        "ref": "T1",
                        "title": "昨天的上线",
                        "summary": "用户说今天下班前要完成上线",
                        "is_due": True,
                    }
                ],
                "knowledge_items": [],
            },
            {"current_desire": "ask_follow_up", "missing_user": "slight"},
            {"elapsed_level": "same_day"},
        )

        self.assertEqual(result["desire"], "ask_follow_up")
        self.assertTrue(result["follow_up"])
        self.assertEqual(result["source_refs"], ["T1"])

    def test_after_work_message_can_express_missing_from_real_time_gap(self):
        result = judge_aura_impulse(
            "我下班了",
            [],
            {"risk_signal": {"requires_safety_gate": False}, "emotion": {}},
            {"items": [], "knowledge_items": []},
            {"current_desire": "express_missing", "missing_user": "clear"},
            {"elapsed_level": "next_day"},
        )

        self.assertEqual(result["desire"], "express_missing")
        self.assertEqual(result["initiative"], "high")

    def test_no_context_cannot_invent_hotpot_preference_or_shared_memory(self):
        result = judge_aura_impulse(
            "晚饭吃什么",
            [],
            {"risk_signal": {"requires_safety_gate": False}, "emotion": {}},
            {"items": [], "knowledge_items": []},
            {"current_desire": "none", "missing_user": "none"},
            {},
        )

        self.assertEqual(result["desire"], "none")
        self.assertEqual(result["source_refs"], [])
        self.assertNotIn("火锅", result["reason"])

    def test_candidate_resolver_can_choose_none(self):
        result = resolve_impulse_candidates(
            [
                {
                    "strength": "low",
                    "desire": "tease",
                    "affection": "subtle",
                    "relevance": 10,
                    "freshness": 10,
                    "interrupt_risk": 90,
                    "reason": "不适合当前对话",
                }
            ]
        )

        self.assertEqual(result["desire"], "none")

    def test_due_thread_and_affect_are_both_candidates_before_resolution(self):
        candidates = collect_impulse_candidates(
            "我下班了",
            [],
            {"risk_signal": {"requires_safety_gate": False}, "emotion": {}},
            {
                "items": [
                    {
                        "ref": "T1",
                        "title": "下班前上线",
                        "summary": "用户说下班前完成上线",
                        "is_due": True,
                    }
                ],
                "knowledge_items": [],
            },
            {
                "current_desire": "show_jealousy",
                "missing_user": "none",
                "jealousy": "low",
                "vulnerability": "medium",
                "active_affects": [{"kind": "jealousy", "decay_phase": "active"}],
            },
            {},
        )

        self.assertEqual(
            {item["source"] for item in candidates},
            {"relationship_thread", "current_affect"},
        )


if __name__ == "__main__":
    unittest.main()
