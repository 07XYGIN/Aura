from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.core.agent.conversation.conversation import aura_agent
from app.core.agent.graph import agent_runtime
from app.core.agent.graph.agent_graph import build_graph


class ConversationTests(TestCase):
    """验证第一阶段聊天链路不依赖旧连续性数据库。"""

    def test_basic_turn_returns_assistant_message(self) -> None:
        previous_graph = agent_runtime.graph
        agent_runtime.graph = build_graph(InMemorySaver())
        try:
            with (
                patch(
                    "app.core.agent.graph.model_node.llm",
                    new=Mock(
                        invoke=Mock(return_value=AIMessage(content="你好"))
                    ),
                ),
                patch(
                    "app.core.agent.conversation.conversation.load_attachments",
                    return_value=[],
                ),
            ):
                events = list(
                    aura_agent(
                        "你好",
                        str(uuid4()),
                        client_message_id="test-turn",
                    )
                )
        finally:
            agent_runtime.graph = previous_graph

        content_events = [event for event in events if event.get("event") == "content"]
        self.assertEqual("".join(event["content"] for event in content_events), "你好")
