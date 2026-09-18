from __future__ import annotations

import json
import unittest

from app.core.activities.registry import ActivityRegistry
from app.core.agent.models import ActivityResult, InteractionMode, TurnRequest
from app.core.agent.orchestrator import TurnOrchestrator
from app.core.agent.protocol import SSEProtocolV1, content_event


class FakeActivity:
    name = "fake"

    async def try_handle(self, _session, request: TurnRequest):
        if request.message != "activity":
            return None
        return ActivityResult(
            activity="fake",
            action="done",
            messages=["完成。"],
        )


class TurnOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_registry_claims_activity_without_router_branching(self) -> None:
        orchestrator = TurnOrchestrator(
            ActivityRegistry([FakeActivity()]),
            activities_enabled=True,
        )

        plan = await orchestrator.prepare(TurnRequest(user_id="u1", message="activity"))

        self.assertEqual(plan.interaction.mode, InteractionMode.ACTIVITY)
        self.assertEqual(plan.activity_result.activity, "fake")

    async def test_branch_turn_bypasses_activity_plugins(self) -> None:
        orchestrator = TurnOrchestrator(
            ActivityRegistry([FakeActivity()]),
            activities_enabled=True,
        )

        plan = await orchestrator.prepare(
            TurnRequest(user_id="u1", message="activity", branch_id="branch-1")
        )

        self.assertEqual(plan.interaction.mode, InteractionMode.NORMAL)
        self.assertIsNone(plan.activity_result)


class SseProtocolV1Tests(unittest.TestCase):
    def test_adds_versioned_envelope_and_keeps_legacy_fields(self) -> None:
        protocol = SSEProtocolV1("turn-1")

        frame = protocol.encode(content_event("你好"))
        payload = json.loads(frame.removeprefix("data: ").strip())

        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["turnId"], "turn-1")
        self.assertEqual(payload["sequence"], 1)
        self.assertEqual(payload["type"], "message.created")
        self.assertEqual(payload["v1Type"], "message.created")
        self.assertEqual(payload["event"], "content")
        self.assertEqual(payload["payload"]["content"], "你好")

    def test_sequence_is_monotonic_within_turn(self) -> None:
        protocol = SSEProtocolV1("turn-1")
        first = json.loads(protocol.encode(content_event("一")).removeprefix("data: ").strip())
        second = json.loads(protocol.encode(content_event("二")).removeprefix("data: ").strip())

        self.assertEqual((first["sequence"], second["sequence"]), (1, 2))


if __name__ == "__main__":
    unittest.main()
