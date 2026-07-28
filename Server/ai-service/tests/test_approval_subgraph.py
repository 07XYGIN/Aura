from __future__ import annotations

import sys
import unittest
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.approval import build_approval_subgraph


class ApprovalSubgraphTest(unittest.TestCase):
    def test_interrupt_waits_for_human_then_resumes_with_decision(self) -> None:
        graph = build_approval_subgraph(InMemorySaver())
        config = {"configurable": {"thread_id": "approval-test", "user_id": "user-test"}}

        paused = graph.invoke(
            {
                "request": {
                    "user_id": "user-test",
                    "public": {"id": "review-1", "title": "要保留吗？"},
                }
            },
            config,
        )
        resumed = graph.invoke(Command(resume={"approved": True}), config)

        self.assertTrue(paused.get("__interrupt__"))
        self.assertEqual(resumed["decision"], {"approved": True})
