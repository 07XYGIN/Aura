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
                        invoke=Mock(return_value=AIMessage(content='{"messages":["你好"]}'))
                    ),
                ),
                patch(
                    "app.core.agent.conversation.conversation.load_attachments",
                    return_value=[],
                ),
                patch(
                    "app.core.agent.conversation.reply.store_reply_timing_state",
                    return_value=True,
                ),
            ):
                events = list(
                    aura_agent(
                        "你好",
                        str(uuid4()),
                        emotion_state={},
                        client_message_id="test-turn",
                    )
                )
        finally:
            agent_runtime.graph = previous_graph

        assistant_events = [event for event in events if event.get("event") == "assistant_message"]
        self.assertEqual([event["content"] for event in assistant_events], ["你好"])
