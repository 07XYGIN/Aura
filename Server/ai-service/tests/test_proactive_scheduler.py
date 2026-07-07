from __future__ import annotations

import unittest
from datetime import UTC, date, datetime, timedelta
from fnmatch import fnmatch
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.core import proactive_scheduler


class FakeRedis:
    def __init__(self):
        self.members: dict[str, float] = {}
        self.values: dict[str, str] = {}

    def zadd(self, _key, mapping):
        self.members.update(mapping)
        return len(mapping)

    def zrangebyscore(self, _key, minimum, maximum, start=0, num=None):
        values = [
            member
            for member, score in self.members.items()
            if float(minimum) <= score <= float(maximum)
        ]
        values.sort(key=lambda member: self.members[member])
        end = None if num is None else start + num
        return values[start:end]

    def zrem(self, _key, *members):
        removed = 0
        for member in members:
            if member in self.members:
                removed += 1
                del self.members[member]
        return removed

    def set(self, key, value):
        self.values[key] = str(value)
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        return int(self.values.pop(key, None) is not None)

    def scan_iter(self, match):
        return [key for key in self.values if fnmatch(key, match)]


class ProactiveSchedulerTest(unittest.IsolatedAsyncioTestCase):
    def test_enqueue_and_pop_due_message_ids(self):
        redis = FakeRedis()
        now = datetime(2026, 7, 4, 10, 0, tzinfo=UTC)
        due_id = str(uuid4())
        future_id = str(uuid4())

        with patch("app.core.proactive_scheduler.get_redis_client", return_value=redis):
            self.assertTrue(proactive_scheduler.enqueue_proactive_message(due_id, now - timedelta(seconds=1)))
            self.assertTrue(proactive_scheduler.enqueue_proactive_message(future_id, now + timedelta(minutes=5)))
            due_ids = proactive_scheduler.pop_due_proactive_message_ids(now=now)

        self.assertEqual(due_ids, [due_id])
        self.assertNotIn(due_id, redis.members)
        self.assertIn(future_id, redis.members)

    async def test_process_due_proactive_messages_marks_sent_and_writes_chat_message(self):
        now = datetime(2026, 7, 4, 10, 0, tzinfo=UTC)
        proactive_id = uuid4()
        user_id = uuid4()
        proactive = SimpleNamespace(
            id=proactive_id,
            user_id=user_id,
            trigger_type="daily_care",
            title="早安",
            content="早呀。",
            scheduled_at=now - timedelta(seconds=1),
            status="pending",
            sent_at=None,
            updated_at=None,
        )

        result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [proactive]))
        session = SimpleNamespace(
            execute=AsyncMock(return_value=result),
            add=unittest.mock.Mock(),
            commit=AsyncMock(),
        )

        sent_count = await proactive_scheduler.process_due_proactive_messages(
            session,
            [str(proactive_id)],
            now=now,
        )

        self.assertEqual(sent_count, 1)
        self.assertEqual(proactive.status, "sent")
        self.assertEqual(proactive.sent_at, now)
        self.assertEqual(session.add.call_count, 2)
        added_records = [call.args[0] for call in session.add.call_args_list]
        self.assertTrue(any(getattr(record, "is_proactive", False) for record in added_records))
        session.commit.assert_awaited_once()

    async def test_enqueue_pending_indexes_future_messages_within_lookahead(self):
        now = datetime(2026, 7, 4, 10, 0, tzinfo=UTC)
        proactive = SimpleNamespace(
            id=uuid4(),
            status="pending",
            scheduled_at=now + timedelta(hours=1),
        )
        result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [proactive]))
        session = SimpleNamespace(execute=AsyncMock(return_value=result))

        with patch("app.core.proactive_scheduler.enqueue_proactive_messages", return_value=1) as enqueue:
            count = await proactive_scheduler.enqueue_pending_proactive_messages(session, now=now)

        self.assertEqual(count, 1)
        enqueue.assert_called_once()

    def test_upcoming_daily_greeting_plans_include_morning_and_evening(self):
        now = datetime(2026, 7, 4, 21, 0, tzinfo=UTC)
        plans = proactive_scheduler.upcoming_daily_greeting_plans_for_user(
            user_id="user-1",
            timezone="Asia/Shanghai",
            now=now,
            lookahead_hours=24,
        )

        self.assertEqual(
            [plan["trigger_type"] for plan in plans],
            [
                proactive_scheduler.MORNING_TRIGGER_TYPE,
                proactive_scheduler.EVENING_TRIGGER_TYPE,
            ],
        )
        self.assertEqual(plans[0]["window"], "06:00:00-08:00:00")
        self.assertEqual(plans[1]["window"], "20:00:00-23:00:00")

    async def test_ensure_daily_greeting_messages_creates_upcoming_slots(self):
        now = datetime(2026, 7, 4, 21, 0, tzinfo=UTC)
        user_id = uuid4()
        session = SimpleNamespace(
            add=unittest.mock.Mock(),
            flush=AsyncMock(),
            commit=AsyncMock(),
        )

        with (
            patch(
                "app.core.proactive_scheduler.load_daily_greeting_targets",
                AsyncMock(
                    return_value=[
                        {
                            "user_id": user_id,
                            "timezone": "Asia/Shanghai",
                            "city_adcode": None,
                        }
                    ]
                ),
            ),
            patch(
                "app.core.proactive_scheduler.daily_greeting_already_planned",
                AsyncMock(return_value=False),
            ),
            patch("app.core.proactive_scheduler.enqueue_proactive_messages", return_value=2) as enqueue,
        ):
            queued_count = await proactive_scheduler.ensure_daily_greeting_messages(session, now=now)

        self.assertEqual(queued_count, 2)
        self.assertEqual(session.add.call_count, 2)
        session.flush.assert_awaited_once()
        session.commit.assert_awaited_once()
        added_records = [call.args[0] for call in session.add.call_args_list]
        self.assertEqual(
            [record.trigger_type for record in added_records],
            [
                proactive_scheduler.MORNING_TRIGGER_TYPE,
                proactive_scheduler.EVENING_TRIGGER_TYPE,
            ],
        )
        enqueue.assert_called_once()

    async def test_daily_greeting_already_planned_checks_local_day_bounds(self):
        result = SimpleNamespace(scalar_one_or_none=lambda: uuid4())
        session = SimpleNamespace(execute=AsyncMock(return_value=result))

        exists = await proactive_scheduler.daily_greeting_already_planned(
            session,
            uuid4(),
            proactive_scheduler.MORNING_TRIGGER_TYPE,
            date(2026, 7, 5),
            "Asia/Shanghai",
        )

        self.assertTrue(exists)
        session.execute.assert_awaited_once()

    async def test_prepare_daily_morning_content_uses_weather_when_city_exists(self):
        user_id = uuid4()
        profile_result = SimpleNamespace(first=lambda: ("Asia/Shanghai", None))
        session = SimpleNamespace(execute=AsyncMock(return_value=profile_result))
        proactive = SimpleNamespace(
            user_id=user_id,
            trigger_type=proactive_scheduler.MORNING_TRIGGER_TYPE,
            content=proactive_scheduler.DAILY_GREETING_PLACEHOLDER,
            metadata_json={"city_adcode": "310000"},
        )

        with (
            patch(
                "app.core.proactive_scheduler.fetch_weather",
                return_value={
                    "status": "1",
                    "city": "上海",
                    "weather": "小雨",
                    "temperature": "24",
                },
            ) as weather,
            patch(
                "app.core.proactive_scheduler.draft_proactive_message_with_llm",
                return_value={
                    "content": "早上好，上海小雨，出门记得带伞。",
                    "tone": "温和",
                    "should_send": True,
                    "source": "llm",
                },
            ),
        ):
            content = await proactive_scheduler.prepare_proactive_message_content(session, proactive)

        self.assertEqual(content, "早上好，上海小雨，出门记得带伞。")
        self.assertEqual(proactive.content, content)
        self.assertEqual(proactive.metadata_json["draft_source"], "llm")
        self.assertEqual(proactive.metadata_json["weather"]["city"], "上海")
        weather.assert_called_once_with("310000")

    def test_collect_due_silence_user_ids_skips_triggered_user(self):
        redis = FakeRedis()
        now = datetime(2026, 7, 4, 10, 0, tzinfo=UTC)
        redis.set("last_user_message:user-1", now.timestamp() - proactive_scheduler.SILENCE_THRESHOLD_SECONDS - 1)
        redis.set("proactive_triggered:user-1", "1")

        with patch("app.core.silence_state.get_redis_client", return_value=redis):
            due_user_ids = proactive_scheduler.collect_due_silence_user_ids(now=now)

        self.assertEqual(due_user_ids, [])

    def test_collect_due_silence_user_ids_skips_deep_night(self):
        redis = FakeRedis()
        now = datetime(2026, 7, 6, 18, 0, tzinfo=UTC)
        redis.set("last_user_message:user-1", now.timestamp() - proactive_scheduler.SILENCE_THRESHOLD_SECONDS - 1)

        with patch("app.core.silence_state.get_redis_client", return_value=redis):
            due_user_ids = proactive_scheduler.collect_due_silence_user_ids(now=now)

        self.assertEqual(due_user_ids, [])

    async def test_trigger_silence_proactive_messages_sends_and_marks_triggered(self):
        now = datetime(2026, 7, 4, 10, 0, tzinfo=UTC)
        user_id = uuid4()
        session = SimpleNamespace(
            add=unittest.mock.Mock(),
            flush=AsyncMock(),
            commit=AsyncMock(),
        )

        with (
            patch(
                "app.core.proactive_scheduler.build_recent_conversation_context",
                AsyncMock(return_value="用户: 今天在准备发布"),
            ),
            patch(
                "app.core.proactive_scheduler.draft_proactive_message_with_llm",
                return_value={
                    "content": "刚刚想到你，过来轻轻放一句问候。",
                    "tone": "温和",
                    "should_send": True,
                    "source": "llm",
                },
            ),
            patch("app.core.proactive_scheduler.append_proactive_history_message", return_value=True) as append_history,
            patch("app.core.proactive_scheduler.mark_silence_proactive_triggered", return_value=True) as mark,
        ):
            sent_count = await proactive_scheduler.trigger_silence_proactive_messages(
                session,
                [str(user_id)],
                now=now,
            )

        self.assertEqual(sent_count, 1)
        session.flush.assert_awaited_once()
        session.commit.assert_awaited_once()
        mark.assert_called_once_with(str(user_id))
        added_records = [call.args[0] for call in session.add.call_args_list]
        self.assertEqual(getattr(added_records[0], "trigger_type", None), "silence")
        self.assertTrue(any(getattr(record, "is_proactive", False) for record in added_records))
        append_history.assert_called_once()
        self.assertEqual(append_history.call_args.kwargs["trigger_type"], "silence")


if __name__ == "__main__":
    unittest.main()
