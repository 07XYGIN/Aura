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

    async def test_process_due_proactive_messages_marks_sent_and_updates_checkpoint(self):
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
            commit=AsyncMock(),
        )

        with patch("app.core.proactive_scheduler.append_proactive_history_message", return_value=True) as append_history:
            sent_count = await proactive_scheduler.process_due_proactive_messages(
                session,
                [str(proactive_id)],
                now=now,
            )

        self.assertEqual(sent_count, 1)
        self.assertEqual(proactive.status, "sent")
        self.assertEqual(proactive.sent_at, now)
        append_history.assert_called_once()
        self.assertEqual(append_history.call_args.kwargs["trigger_type"], "daily_care")
        self.assertEqual(session.commit.await_count, 2)

    async def test_failed_checkpoint_write_retries_with_stable_delivery_id(self):
        now = datetime(2026, 7, 4, 10, 0, tzinfo=UTC)
        proactive = SimpleNamespace(
            id=uuid4(),
            user_id=uuid4(),
            trigger_type="follow_up",
            title="跟进",
            content="昨天那个接口后来通了吗？",
            scheduled_at=now,
            sent_at=None,
            status="processing",
            attempt_count=1,
            delivery_message_id="stable-delivery-1",
            claimed_until=now + timedelta(minutes=5),
            last_error=None,
            updated_at=None,
        )
        session = SimpleNamespace(commit=AsyncMock())

        with patch(
            "app.core.proactive_scheduler.append_proactive_history_message",
            return_value=False,
        ) as append_history:
            sent_count = await proactive_scheduler.send_proactive_message_records(
                session,
                [proactive],
                now=now,
            )

        self.assertEqual(sent_count, 0)
        self.assertEqual(proactive.status, "pending")
        self.assertEqual(proactive.scheduled_at, now + timedelta(seconds=60))
        self.assertEqual(proactive.last_error, "聊天历史写入失败")
        self.assertIsNone(proactive.claimed_until)
        self.assertEqual(append_history.call_args.kwargs["message_id"], "stable-delivery-1")
        session.commit.assert_awaited_once()

    async def test_relationship_follow_up_requires_explicit_server_authorization(self):
        now = datetime(2026, 7, 24, 2, 0, tzinfo=UTC)
        unauthorized = SimpleNamespace(
            id=uuid4(),
            user_id=uuid4(),
            title="普通未来事项",
            summary="明天发布接口",
            version=1,
            metadata_json={"proactive_allowed": False},
        )
        authorized = SimpleNamespace(
            id=uuid4(),
            user_id=unauthorized.user_id,
            title="面试结果",
            summary="记得问面试结果",
            version=1,
            metadata_json={"proactive_allowed": True},
        )
        # SQL 已在数据库层过滤授权值，这里的假结果只返回已授权线程。
        result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [authorized]))
        session = SimpleNamespace(
            execute=AsyncMock(return_value=result),
            add=unittest.mock.Mock(),
            flush=AsyncMock(),
            commit=AsyncMock(),
            rollback=AsyncMock(),
        )
        with patch("app.core.proactive_scheduler.enqueue_proactive_messages", return_value=1):
            count = await proactive_scheduler.ensure_relationship_follow_up_messages(
                session,
                now=now,
            )

        self.assertEqual(count, 1)
        record = session.add.call_args.args[0]
        self.assertEqual(record.trigger_type, "relationship_follow_up")
        self.assertIn(str(authorized.id), record.dedupe_key)
        self.assertEqual(record.metadata_json["relationship_thread_id"], str(authorized.id))
        self.assertNotIn(str(unauthorized.id), record.dedupe_key)

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

    def test_upcoming_daily_greeting_plans_do_not_reschedule_missed_slot_to_now(self):
        now = datetime(2026, 7, 4, 0, 30, tzinfo=UTC)

        def fake_daily_plan(*, target_date, **_kwargs):
            return {
                "date": target_date.isoformat(),
                "morning": {
                    "scheduled_at": datetime.combine(
                        target_date,
                        datetime.min.time().replace(hour=8),
                        tzinfo=proactive_scheduler.ZoneInfo("Asia/Shanghai"),
                    ).isoformat(),
                    "window": "06:00:00-08:00:00",
                    "reply_spec": "morning",
                },
                "evening": {
                    "scheduled_at": datetime.combine(
                        target_date,
                        datetime.min.time().replace(hour=21),
                        tzinfo=proactive_scheduler.ZoneInfo("Asia/Shanghai"),
                    ).isoformat(),
                    "window": "20:00:00-23:00:00",
                    "reply_spec": "evening",
                },
            }

        with patch(
            "app.core.proactive_scheduler.build_daily_greeting_plan",
            side_effect=fake_daily_plan,
        ):
            plans = proactive_scheduler.upcoming_daily_greeting_plans_for_user(
                user_id="user-1",
                timezone="Asia/Shanghai",
                now=now,
                lookahead_hours=24,
            )

        self.assertIn(
            proactive_scheduler.EVENING_TRIGGER_TYPE,
            [plan["trigger_type"] for plan in plans],
        )
        self.assertFalse(
            any(
                plan["trigger_type"] == proactive_scheduler.MORNING_TRIGGER_TYPE
                and plan["greeting_date"] == "2026-07-04"
                for plan in plans
            )
        )

    async def test_stale_daily_greeting_is_skipped_instead_of_sent(self):
        now = datetime(2026, 7, 4, 10, 0, tzinfo=UTC)
        proactive = SimpleNamespace(
            id=uuid4(),
            user_id=uuid4(),
            trigger_type=proactive_scheduler.MORNING_TRIGGER_TYPE,
            title="morning",
            content=proactive_scheduler.DAILY_GREETING_PLACEHOLDER,
            scheduled_at=now - timedelta(hours=2),
            status="pending",
            sent_at=None,
            updated_at=None,
            metadata_json={},
        )
        session = SimpleNamespace(
            add=unittest.mock.Mock(),
            flush=AsyncMock(),
            commit=AsyncMock(),
        )

        sent_count = await proactive_scheduler.send_proactive_message_records(
            session,
            [proactive],
            now=now,
        )

        self.assertEqual(sent_count, 0)
        self.assertEqual(proactive.status, "skipped")
        self.assertEqual(proactive.metadata_json["skipped_reason"], "stale_daily_greeting")
        session.add.assert_not_called()
        session.flush.assert_not_awaited()
        session.commit.assert_awaited_once()

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
        self.assertEqual(session.flush.await_count, 1)
        session.commit.assert_awaited_once()
        mark.assert_called_once_with(str(user_id))
        added_records = [call.args[0] for call in session.add.call_args_list]
        self.assertEqual(getattr(added_records[0], "trigger_type", None), "silence")
        self.assertEqual(len(added_records), 1)
        append_history.assert_called_once()
        self.assertEqual(append_history.call_args.kwargs["trigger_type"], "silence")

    async def test_scheduler_loop_waits_before_first_tick(self):
        stop_event = proactive_scheduler.asyncio.Event()

        with (
            patch("app.core.proactive_scheduler.AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS", 60),
            patch("app.core.proactive_scheduler.run_proactive_scheduler_tick", AsyncMock()) as tick,
        ):
            task = proactive_scheduler.asyncio.create_task(
                proactive_scheduler.proactive_scheduler_loop(stop_event)
            )
            await proactive_scheduler.asyncio.sleep(0)
            tick.assert_not_awaited()

            stop_event.set()
            await task
            tick.assert_not_awaited()

    async def test_daily_state_failure_does_not_stop_persistent_outbox(self):
        """每日生活投影失败时应回滚该事务，但仍继续领取并发送已有主动消息。"""

        now = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
        session = SimpleNamespace(rollback=AsyncMock())

        class SessionContext:
            async def __aenter__(self):
                return session

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        with (
            patch("app.core.proactive_scheduler.AsyncSessionLocal", return_value=SessionContext()),
            patch("app.core.proactive_scheduler.redis_available", return_value=False),
            patch(
                "app.core.proactive_scheduler.ensure_daily_states_async",
                AsyncMock(side_effect=RuntimeError("daily unavailable")),
            ),
            patch(
                "app.core.proactive_scheduler.trigger_silence_proactive_messages",
                AsyncMock(return_value=0),
            ),
            patch(
                "app.core.proactive_scheduler.ensure_daily_greeting_messages",
                AsyncMock(return_value=0),
            ),
            patch(
                "app.core.proactive_scheduler.ensure_relationship_follow_up_messages",
                AsyncMock(return_value=0),
            ),
            patch(
                "app.core.proactive_scheduler.claim_due_proactive_messages",
                AsyncMock(return_value=[]),
            ) as claim,
            patch(
                "app.core.proactive_scheduler.send_proactive_message_records",
                AsyncMock(return_value=0),
            ) as send,
        ):
            sent_count = await proactive_scheduler.run_proactive_scheduler_tick(now=now)

        self.assertEqual(sent_count, 0)
        session.rollback.assert_awaited_once()
        claim.assert_awaited_once_with(session, now=now)
        send.assert_awaited_once_with(session, [], now=now)


if __name__ == "__main__":
    unittest.main()
