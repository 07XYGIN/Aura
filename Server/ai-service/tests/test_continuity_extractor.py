from __future__ import annotations

import unittest
from datetime import UTC, datetime
from uuid import uuid4

from app.core.continuity.extractor import (
    build_source_key,
    deterministic_thread_hints,
    normalize_thread_candidates,
)


class ContinuityExtractorTest(unittest.TestCase):
    """验证关系线程抽取只接受高置信度、可幂等的候选。"""

    def setUp(self) -> None:
        self.now = datetime(2026, 7, 23, 2, 0, tzinfo=UTC)

    def test_model_cannot_authorize_proactive_follow_up_on_its_own(self) -> None:
        raw = [{
            "operation": "create",
            "thread_type": "follow_up",
            "title": "面试结果",
            "summary": "小乔明天要面试",
            "follow_up_at": "2026-07-24T10:00:00+08:00",
            "proactive_allowed": True,
        }]

        candidates = normalize_thread_candidates(raw, "我明天要面试", now=self.now)

        self.assertEqual(len(candidates), 1)
        self.assertFalse(candidates[0]["proactive_allowed"])
        self.assertEqual(candidates[0]["follow_up_at"], "2026-07-24T02:00:00+00:00")

    def test_explicit_reminder_authorization_is_preserved(self) -> None:
        raw = [{
            "operation": "create",
            "thread_type": "follow_up",
            "title": "面试结果",
            "summary": "明天面试结束后询问结果",
            "follow_up_at": "2026-07-24T10:00:00+08:00",
            "proactive_allowed": True,
        }]

        candidates = normalize_thread_candidates(raw, "明天面试，记得问我结果", now=self.now)

        self.assertTrue(candidates[0]["proactive_allowed"])
        self.assertTrue(
            normalize_thread_candidates(
                raw,
                "后天别忘了提醒我看结果",
                now=self.now,
            )[0]["proactive_allowed"]
        )

    def test_state_operation_without_explicit_target_is_discarded(self) -> None:
        candidates = normalize_thread_candidates(
            [{
                "operation": "resolve",
                "thread_type": "open_item",
                "title": "接口问题",
                "summary": "已经解决",
            }],
            "那个接口已经解决了",
            now=self.now,
        )

        self.assertEqual(candidates, [])

    def test_unknown_enum_values_are_discarded_instead_of_defaulted(self) -> None:
        candidates = normalize_thread_candidates(
            [{
                "operation": "invent",
                "thread_type": "anything",
                "world_layer": "system",
                "title": "不应保存",
                "summary": "无效模型输出",
            }],
            "普通消息",
            now=self.now,
        )
        self.assertEqual(candidates, [])

    def test_deterministic_hint_detects_future_task_without_scheduling(self) -> None:
        candidates = deterministic_thread_hints("我明天要面试，今晚先准备一下", now=self.now)

        self.assertEqual(candidates[0]["thread_type"], "open_item")
        self.assertFalse(candidates[0]["proactive_allowed"])
        self.assertEqual(candidates[0]["follow_up_at"], "2026-07-24T02:00:00+00:00")

    def test_deterministic_hint_rejects_trivial_and_hypothetical_future_text(self) -> None:
        self.assertEqual(deterministic_thread_hints("明天见", now=self.now), [])
        self.assertEqual(
            deterministic_thread_hints("如果明天要面试，我可能会紧张", now=self.now),
            [],
        )

    def test_denied_reminder_and_cancelled_plan_never_create_follow_up(self) -> None:
        self.assertEqual(
            deterministic_thread_hints("明天不用提醒我面试了", now=self.now),
            [],
        )
        self.assertEqual(
            deterministic_thread_hints("我明天不去面试了，已经取消", now=self.now),
            [],
        )
        self.assertEqual(
            normalize_thread_candidates(
                [{
                    "operation": "create",
                    "thread_type": "follow_up",
                    "title": "面试",
                    "summary": "明天询问面试",
                    "proactive_allowed": True,
                }],
                "明天不用提醒我面试了",
                now=self.now,
            ),
            [],
        )

    def test_deterministic_hint_records_direct_interaction_correction(self) -> None:
        candidates = deterministic_thread_hints("你又理解错了，我不是想让你安慰我", now=self.now)

        self.assertEqual(candidates[0]["thread_type"], "conflict")
        self.assertEqual(candidates[0]["world_layer"], "shared_history")

    def test_source_key_is_stable_and_scoped_to_message(self) -> None:
        user_id = str(uuid4())
        candidate = {
            "operation": "create",
            "thread_type": "open_item",
            "perspective": "user",
            "world_layer": "reality",
            "title": "发布",
            "summary": "明天发布",
            "target_id": None,
            "follow_up_at": None,
            "proactive_allowed": False,
        }

        first = build_source_key(user_id, "message-1", candidate)
        reordered = build_source_key(user_id, "message-1", dict(reversed(list(candidate.items()))))
        second_message = build_source_key(user_id, "message-2", candidate)

        self.assertEqual(first, reordered)
        self.assertNotEqual(first, second_message)


if __name__ == "__main__":
    unittest.main()
