from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from pydantic import ValidationError

from app.core.continuity.capsule_extractor import (
    has_explicit_conditional_authorization,
    normalize_conditional_message_candidates,
)
from app.core.continuity.capsules import (
    build_create_values,
    conditional_message_dict,
    github_event_matches,
    keyword_matches,
    project_status_matches,
    queue_record,
    stage_conditional_message_delivery_state,
    text_digest,
    verify_secret,
)
from app.core.agent.protocol import memory_candidate_event
from app.core.logging_config import sanitize_sql_parameters, to_log_text
from app.db.models import ConditionalMessage
from app.schemas.capsule import ConditionalMessageCreateRequest


class ConditionalMessageDomainTest(unittest.IsolatedAsyncioTestCase):
    """验证条件授权、密封边界、匹配规则和 outbox 状态衔接。"""

    def test_model_cannot_authorize_plain_future_statement(self) -> None:
        raw = [
            {
                "authorized": True,
                "message_type": "time_capsule",
                "condition_type": "time",
                "title": "面试",
                "content": "明天要面试",
                "deliver_at": "2026-07-24T02:00:00+00:00",
                "condition": {},
                "evidence": "明天要面试",
            }
        ]

        result = normalize_conditional_message_candidates(
            raw,
            "明天要面试",
            now=datetime(2026, 7, 23, tzinfo=UTC),
        )

        self.assertEqual(result, [])
        self.assertFalse(has_explicit_conditional_authorization("明天要面试"))

    def test_explicit_future_delivery_keeps_only_verbatim_content(self) -> None:
        source = "等到明天晚上，把‘别忘了你已经做了很多’发给我"
        raw = [
            {
                "authorized": True,
                "message_type": "time_capsule",
                "condition_type": "time",
                "title": "明晚打开",
                "content": "别忘了你已经做了很多",
                "deliver_at": "2026-07-24T12:00:00+00:00",
                "condition": {},
                "evidence": "把‘别忘了你已经做了很多’发给我",
            }
        ]

        result = normalize_conditional_message_candidates(
            raw,
            source,
            now=datetime(2026, 7, 23, tzinfo=UTC),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["content"], "别忘了你已经做了很多")
        self.assertEqual(result[0]["conditionType"], "time")

        invented = [{**raw[0], "content": "模型自己补写的话"}]
        self.assertEqual(
            normalize_conditional_message_candidates(
                invented,
                source,
                now=datetime(2026, 7, 23, tzinfo=UTC),
            ),
            [],
        )

    def test_denial_overrides_explicit_words(self) -> None:
        self.assertFalse(
            has_explicit_conditional_authorization("算了，不要保存成时间胶囊，明天也不用发给我")
        )

    def test_request_schema_requires_condition_specific_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ConditionalMessageCreateRequest(
                messageType="time_capsule",
                conditionType="time",
                title="缺时间",
                content="正文",
                clientRequestId="request-1",
            )
        with self.assertRaises(ValidationError):
            ConditionalMessageCreateRequest(
                messageType="secret_vault",
                conditionType="github_event",
                title="缺仓库",
                content="正文",
                condition={"event": "workflow_run"},
                clientRequestId="request-2",
            )

    def test_passphrase_is_hashed_and_compared_exactly(self) -> None:
        request = ConditionalMessageCreateRequest(
            messageType="secret_vault",
            conditionType="passphrase",
            title="保险箱",
            content="密封正文",
            passphrase=" 贴贴 ",
            clientRequestId="request-passphrase",
        )

        values = build_create_values(uuid4(), request, datetime.now(UTC))

        self.assertNotEqual(values["unlock_secret_hash"], " 贴贴 ")
        self.assertTrue(verify_secret(" 贴贴 ", values["unlock_secret_hash"]))
        self.assertFalse(verify_secret("贴贴", values["unlock_secret_hash"]))

    def test_creation_metadata_cannot_forge_authorization_or_echo_secret(self) -> None:
        request = ConditionalMessageCreateRequest(
            messageType="secret_vault",
            conditionType="keyword",
            title="关键词保险箱",
            content="密封正文",
            condition={"keyword": "再试一次"},
            clientRequestId="request-metadata",
            metadata={
                "authorized_by_user": True,
                "proactive_allowed": True,
                "content": "密封正文",
                "passphrase": "秘密",
                "label": "保留标签",
            },
        )

        values = build_create_values(uuid4(), request, datetime.now(UTC))

        self.assertEqual(values["metadata_json"], {"label": "保留标签"})

    def test_keyword_matching_rejects_negated_false_positive(self) -> None:
        condition = {"keyword": "想放弃", "matchMode": "contains"}

        self.assertTrue(keyword_matches(condition, "我又有点想放弃了"))
        self.assertFalse(keyword_matches(condition, "我现在不想放弃"))
        self.assertFalse(keyword_matches({**condition, "matchMode": "exact"}, "有点想放弃"))
        self.assertNotIn("想放弃", text_digest("我又有点想放弃了"))

    def test_project_and_github_conditions_require_all_declared_fields(self) -> None:
        self.assertTrue(
            project_status_matches(
                {"projectKey": "aura", "expectedStatus": "released"},
                {"projectKey": "Aura", "status": "RELEASED"},
            )
        )
        self.assertFalse(
            project_status_matches(
                {"projectKey": "aura", "expectedStatus": "released"},
                {"projectKey": "other", "status": "released"},
            )
        )
        condition = {
            "repository": "07xygin/aura",
            "event": "workflow_run",
            "conclusion": "success",
            "ref": "refs/heads/main",
        }
        self.assertTrue(github_event_matches(condition, dict(condition)))
        self.assertFalse(github_event_matches(condition, {**condition, "conclusion": "failure"}))

    def test_sealed_snapshot_never_returns_content_or_secret_hash(self) -> None:
        now = datetime.now(UTC)
        record = SimpleNamespace(
            id=uuid4(),
            message_type="secret_vault",
            condition_type="passphrase",
            title="密封",
            content="不能提前出现的正文",
            status="sealed",
            deliver_at=None,
            condition_json={},
            triggered_at=None,
            delivered_at=None,
            cancelled_at=None,
            expires_at=None,
            version=1,
            created_at=now,
            updated_at=now,
            metadata_json={},
            unlock_secret_hash="不能出现的摘要",
        )

        payload = conditional_message_dict(record)

        self.assertIsNone(payload["content"])
        self.assertTrue(payload["contentSealed"])
        self.assertNotIn("unlockSecretHash", payload)
        self.assertNotIn("不能提前出现的正文", str(payload))

    def test_matching_condition_queues_one_stable_outbox(self) -> None:
        now = datetime.now(UTC)
        record = SimpleNamespace(
            id=uuid4(),
            user_id=uuid4(),
            message_type="time_capsule",
            condition_type="time",
            title="未来",
            content="给未来的话",
            status="sealed",
            expires_at=now + timedelta(days=1),
            version=1,
            outbox_message_id=None,
            triggered_at=None,
        )
        session = MagicMock()

        outbox = queue_record(session, record, now, "time", {"deliverAt": now.isoformat()})

        self.assertIsNotNone(outbox)
        self.assertEqual(record.status, "queued")
        self.assertEqual(record.outbox_message_id, outbox.id)
        self.assertEqual(outbox.dedupe_key, f"conditional_message:{record.id}:1")
        self.assertEqual(outbox.metadata_json["conditional_message_id"], str(record.id))
        self.assertNotIn("给未来的话", str(outbox.metadata_json))

    async def test_sent_outbox_marks_source_delivered_idempotently(self) -> None:
        now = datetime.now(UTC)
        outbox_id = uuid4()
        user_id = uuid4()
        proactive = SimpleNamespace(
            id=outbox_id,
            user_id=user_id,
            trigger_type="conditional_message",
            status="sent",
            metadata_json={"conditional_message_id": str(uuid4())},
        )
        record = SimpleNamespace(
            id=uuid4(),
            outbox_message_id=outbox_id,
            status="queued",
            delivered_at=None,
            version=2,
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = record
        session = SimpleNamespace(execute=AsyncMock(return_value=result))

        changed = await stage_conditional_message_delivery_state(session, proactive, now)
        replayed = await stage_conditional_message_delivery_state(session, proactive, now)

        self.assertTrue(changed)
        self.assertFalse(replayed)
        self.assertEqual(record.status, "delivered")
        self.assertEqual(record.delivered_at, now)
        self.assertEqual(record.version, 3)

    def test_sealed_content_and_passphrase_are_redacted_from_verbose_logs(self) -> None:
        statement = (
            "INSERT INTO conditional_message (title, content, unlock_secret_hash) "
            "VALUES ($1, $2, $3)"
        )
        sanitized = sanitize_sql_parameters(
            statement,
            ("标题", "密封正文", "口令摘要"),
        )
        self.assertEqual(sanitized, ["标题", "***", "***"])
        self.assertEqual(
            sanitize_sql_parameters("SELECT 1", {"passphrase": "秘密", "event_id": "e1"}),
            {"passphrase": "***", "event_id": "e1"},
        )

        record = ConditionalMessage(
            user_id=uuid4(),
            message_type="secret_vault",
            condition_type="passphrase",
            title="密封",
            content="不能进入日志的正文",
            status="sealed",
            condition_json={},
            unlock_secret_hash="不能进入日志的摘要",
            dedupe_key="request:log-test",
        )
        preview = to_log_text(record)
        self.assertNotIn("不能进入日志的正文", preview)
        self.assertNotIn("不能进入日志的摘要", preview)

    def test_memory_candidate_sse_does_not_echo_sealed_content_or_passphrase(self) -> None:
        event = memory_candidate_event(
            {
                "save": False,
                "conditional_messages": [
                    {
                        "authorized": True,
                        "messageType": "secret_vault",
                        "conditionType": "passphrase",
                        "title": "保险箱",
                        "content": "不能通过 SSE 泄露的正文",
                        "passphrase": "不能通过 SSE 泄露的口令",
                        "condition": {"keyword": "秘密"},
                    }
                ],
            }
        )

        serialized = str(event)
        self.assertNotIn("不能通过 SSE 泄露的正文", serialized)
        self.assertNotIn("不能通过 SSE 泄露的口令", serialized)
        self.assertNotIn("keyword", serialized)
        self.assertEqual(
            event["memory_candidate"]["conditional_messages"][0]["title"],
            "保险箱",
        )


if __name__ == "__main__":
    unittest.main()
