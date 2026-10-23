from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent import agent_graph


class ConversationBranchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = agent_graph.build_graph(InMemorySaver())
        self.user_id = "branch-user"
        self.config = {"configurable": {"thread_id": self.user_id, "user_id": self.user_id}}
        self.graph.update_state(
            self.config,
            {
                "user_id": self.user_id,
                "messages": [
                    HumanMessage(id="human-1", content="你好"),
                    AIMessage(id="ai-1", content="你好。"),
                    HumanMessage(id="human-2", content="再说一点"),
                    AIMessage(id="ai-2", content="好。"),
                ],
            },
        )
        self.aura_patch = patch("app.core.agent.agent_graph.aura", self.graph)
        self.aura_patch.start()

    def tearDown(self) -> None:
        self.aura_patch.stop()

    def test_creates_isolated_branch_from_selected_message(self) -> None:
        branch_id = agent_graph.create_history_branch(self.user_id, "ai-1")

        self.assertIsNotNone(branch_id)
        assert branch_id is not None
        self.assertEqual(
            [item["content"] for item in agent_graph.get_history(self.user_id, branch_id)],
            ["你好", "你好。"],
        )
        self.assertEqual(
            [item["content"] for item in agent_graph.get_history(self.user_id)],
            ["你好", "你好。", "再说一点", "好。"],
        )

    def test_retry_creates_new_branch_before_replaying_user_message(self) -> None:
        with patch(
            "app.core.agent.agent_graph.aura_agent",
            return_value=iter([{"event": "content", "content": "新的回复"}]),
        ) as replay:
            events = list(agent_graph.retry_aura_agent(self.user_id, "ai-2"))

        self.assertEqual(events[0]["event"], "conversation_branch")
        self.assertEqual(events[1]["content"], "新的回复")
        self.assertEqual(replay.call_args.args[0], "再说一点")
        self.assertTrue(replay.call_args.kwargs["branch_id"].startswith("b-"))


if __name__ == "__main__":
    unittest.main()
