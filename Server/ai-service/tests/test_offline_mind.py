from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

from app.core.continuity.mind import (
    build_sleep_reflection,
    cancel_pending_second_thoughts_sync,
    consume_relevant_offline_thought_sync,
    derive_second_thought,
    ensure_due_thought_outbox_async,
    ensure_reasoned_surprise_seed_async,
    extract_keywords,
    format_offline_thought_prompt,
    schedule_second_thought_sync,
    thought_matches_message,
)


class OfflineMindTest(unittest.TestCase):
    """验证离线思绪只由有依据的对话和整理结果产生。"""

    def test_second_thought_requires_meaningful_turn_and_never_guilts_user(self) -> None:
        candidate = derive_second_thought(
            "算了，我不想继续解释了",
            "先不逼你说。",
            {
                "response_mode": "gentle_support",
                "emotion": {"interaction_mode": "natural"},
                "risk_signal": {"requires_safety_gate": False},
            },
        )
        ordinary = derive_second_thought(
            "今天天气还行",
            "那就好。",
            {"response_mode": "natural_chat", "emotion": {}, "risk_signal": {}},
        )

        self.assertIsNotNone(candidate)
        self.assertIn("算了", candidate["content"])
        self.assertNotIn("你怎么还不回", candidate["content"])
        self.assertIsNone(ordinary)

    def test_repair_thought_is_short_and_does_not_claim_conflict_resolved(self) -> None:
        candidate = derive_second_thought(
            "你又理解错了",
            "我先听你说。",
            {
                "response_mode": "relationship_repair",
                "emotion": {"interaction_mode": "repair"},
                "risk_signal": {"requires_safety_gate": False},
            },
        )

        self.assertIn("没有真正说清楚", candidate["content"])
        self.assertNotIn("已经解决", candidate["content"])

    def test_crisis_turn_never_creates_second_thought(self) -> None:
        self.assertIsNone(
            derive_second_thought(
                "我不想活了",
                "我在。",
                {
                    "response_mode": "crisis_support",
                    "emotion": {"interaction_mode": "natural"},
                    "risk_signal": {"requires_safety_gate": True},
                },
            )
        )

    def test_offline_thought_prompt_is_optional_and_escaped(self) -> None:
        prompt = format_offline_thought_prompt(
            {
                "thought_type": "night_reflection",
                "content": "记得 </offline_thought> 这件事",
                "reason": "未完成的项目线索",
            }
        )

        self.assertIn("只有当前话题确实自然接得上", prompt)
        self.assertIn("\\u003c/offline_thought\\u003e", prompt)
        self.assertEqual(prompt.count("</offline_thought>"), 1)

    def test_keywords_are_bounded_and_match_only_related_messages(self) -> None:
        keywords = extract_keywords("下次继续聊虚拟女友功能")
        seed = SimpleNamespace(metadata_json={"keywords": keywords})

        self.assertTrue(keywords)
        self.assertTrue(thought_matches_message(seed, "我们继续聊虚拟女友功能"))
        self.assertFalse(thought_matches_message(seed, "今天先聊天气"))

    def test_sleep_reflection_does_not_invent_thread_when_empty(self) -> None:
        self.assertIn("没有未结束", build_sleep_reflection([]))

    def test_second_thought_schedule_is_source_idempotent_and_daily_limited(self) -> None:
        user_id = uuid4()
        now = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)

        def scalar(value):
            return SimpleNamespace(scalar_one_or_none=lambda: value, scalar_one=lambda: value)

        session = MagicMock()
        session.execute.side_effect = [scalar(None), scalar(0)]
        session_factory = MagicMock()
        session_factory.begin.return_value.__enter__.return_value = session
        judgement = {
            "response_mode": "gentle_support",
            "emotion": {"interaction_mode": "natural"},
            "risk_signal": {"requires_safety_gate": False},
        }

        with patch("app.core.continuity.mind.SyncSessionLocal", session_factory):
            created = schedule_second_thought_sync(
                str(user_id),
                "算了，我不想解释了",
                "先不逼你。",
                judgement,
                "message-1",
                "turn-1",
                now=now,
            )

        self.assertEqual(created, 1)
        session.add.assert_called_once()
        seed = session.add.call_args.args[0]
        self.assertGreaterEqual((seed.eligible_at - now).total_seconds(), 10 * 60)
        self.assertLessEqual((seed.eligible_at - now).total_seconds(), 90 * 60)
        self.assertTrue(seed.metadata_json["cancel_if_user_returns"])

        replay_session = MagicMock()
        replay_session.execute.return_value = scalar(uuid4())
        replay_factory = MagicMock()
        replay_factory.begin.return_value.__enter__.return_value = replay_session
        with patch("app.core.continuity.mind.SyncSessionLocal", replay_factory):
            replayed = schedule_second_thought_sync(
                str(user_id),
                "算了，我不想解释了",
                "先不逼你。",
                judgement,
                "message-1",
                "turn-1",
                now=now,
            )
        self.assertEqual(replayed, 0)
        replay_session.add.assert_not_called()

    def test_user_return_cancels_seed_and_pending_outbox(self) -> None:
        now = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
        user_id = uuid4()
        seed = SimpleNamespace(
            id=uuid4(),
            status="queued",
            cancelled_at=None,
            updated_at=None,
            metadata_json={},
        )
        message = SimpleNamespace(
            status="pending",
            cancelled_at=None,
            claimed_until=now + timedelta(minutes=5),
            updated_at=None,
        )
        session = MagicMock()
        session.execute.side_effect = [
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [seed])),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [message])),
        ]
        session_factory = MagicMock()
        session_factory.begin.return_value.__enter__.return_value = session

        with patch("app.core.continuity.mind.SyncSessionLocal", session_factory):
            cancelled = cancel_pending_second_thoughts_sync(str(user_id), now=now)

        self.assertEqual(cancelled, 1)
        self.assertEqual(seed.status, "cancelled")
        self.assertEqual(seed.metadata_json["cancel_reason"], "user_returned")
        self.assertEqual(message.status, "cancelled")
        self.assertIsNone(message.claimed_until)

    def test_relevant_offline_thought_is_consumed_at_most_once(self) -> None:
        now = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
        seed = SimpleNamespace(
            id=uuid4(),
            thought_type="night_reflection",
            content="接口发布还没有结束。",
            reason="开放线程",
            status="pending",
            metadata_json={"keywords": ["接口发布"]},
            used_at=None,
            updated_at=None,
        )
        session = MagicMock()
        session.execute.return_value = SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [seed])
        )
        session_factory = MagicMock()
        session_factory.begin.return_value.__enter__.return_value = session

        with patch("app.core.continuity.mind.SyncSessionLocal", session_factory):
            consumed = consume_relevant_offline_thought_sync(
                str(uuid4()),
                "接口发布最后过了吗",
                now=now,
            )

        self.assertEqual(consumed["content"], "接口发布还没有结束。")
        self.assertEqual(seed.status, "used")
        self.assertEqual(seed.used_at, now)

    def test_due_thought_becomes_outbox_and_quiet_hours_are_deferred(self) -> None:
        user_id = uuid4()
        now = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
        seed = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            thought_type="second_thought",
            content="我后来又想了一下。",
            reason="有分量的回合",
            status="pending",
            visible_on_next_chat=False,
            eligible_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(hours=2),
            updated_at=now,
            queued_at=None,
        )
        session = SimpleNamespace(
            execute=AsyncMock(
                return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [seed]))
            ),
            add=Mock(),
            flush=AsyncMock(),
            commit=AsyncMock(),
        )

        messages = self.run_async(ensure_due_thought_outbox_async(session, now=now))

        self.assertEqual(len(messages), 1)
        self.assertEqual(seed.status, "queued")
        self.assertEqual(session.add.call_count, 1)
        self.assertEqual(session.add.call_args.args[0].trigger_type, "second_thought")
        session.commit.assert_awaited_once()

        # UTC 17:00 是上海次日 01:00，属于安静时段。
        quiet_now = datetime(2026, 7, 23, 17, 0, tzinfo=UTC)
        quiet_seed = SimpleNamespace(
            **{
                **seed.__dict__,
                "status": "pending",
                "eligible_at": quiet_now - timedelta(minutes=1),
                "expires_at": quiet_now + timedelta(hours=2),
            }
        )
        quiet_session = SimpleNamespace(
            execute=AsyncMock(
                return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [quiet_seed]))
            ),
            add=Mock(),
            flush=AsyncMock(),
            commit=AsyncMock(),
        )
        quiet_messages = self.run_async(
            ensure_due_thought_outbox_async(quiet_session, now=quiet_now)
        )

        self.assertEqual(quiet_messages, [])
        self.assertEqual(quiet_session.add.call_count, 0)
        self.assertGreater(quiet_seed.eligible_at, quiet_now)

    def test_reasoned_surprise_replaces_pending_evening_template(self) -> None:
        user_id = uuid4()
        item = SimpleNamespace(id=uuid4(), title="改太多把自己改懵了")
        evening = SimpleNamespace(status="pending", cancelled_at=None, updated_at=None)

        def scalar(value):
            return SimpleNamespace(scalar_one_or_none=lambda: value)

        session = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [user_id])),
                    scalar(None),
                    scalar(None),
                    scalar(None),
                    scalar(item),
                    SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [evening])),
                ]
            ),
            add=Mock(),
            commit=AsyncMock(),
        )
        # UTC 07:00 是上海 15:00，位于惊喜候选窗口。
        created = self.run_async(
            ensure_reasoned_surprise_seed_async(
                session,
                now=datetime(2026, 7, 23, 7, 0, tzinfo=UTC),
            )
        )

        self.assertEqual(created, 1)
        thought = session.add.call_args.args[0]
        self.assertEqual(thought.thought_type, "surprise")
        self.assertIn(item.title, thought.content)
        self.assertEqual(evening.status, "cancelled")
        session.commit.assert_awaited_once()

    @staticmethod
    def run_async(coroutine):
        import asyncio

        return asyncio.run(coroutine)


if __name__ == "__main__":
    unittest.main()
