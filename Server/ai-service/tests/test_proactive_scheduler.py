from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.core import proactive_scheduler


class FakeRedis:
    def __init__(self):
        self.members: dict[str, float] = {}

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


if __name__ == "__main__":
    unittest.main()
