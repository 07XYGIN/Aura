import sys
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.agent_graph import build_runtime_system_prompt, should_continue, tools, trim_short_term_messages, turn_judge


class AgentGraphTest(unittest.TestCase):
    def test_should_continue_ends_when_history_is_empty(self):
        self.assertEqual(should_continue({"messages": []}), END)

    def test_should_continue_ends_when_messages_missing(self):
        self.assertEqual(should_continue({}), END)

    def test_turn_judge_uses_precomputed_judgement(self):
        judgement = {
            "emotion": {"user_emotion": "lonely", "support_needed": True},
            "relationship_delta": {"label": "靠近"},
            "memory_candidate": {"save": False, "memory_scope": "short"},
            "risk_signal": {"level": "none", "requires_safety_gate": False},
            "response_mode": "lonely_support",
        }

        result = turn_judge({"messages": [], "turn_judgement": judgement})

        self.assertEqual(result["emotion"]["user_emotion"], "lonely")
        self.assertEqual(result["turn_judgement"]["response_mode"], "lonely_support")

    def test_runtime_prompt_includes_turn_judgement_context(self):
        prompt = build_runtime_system_prompt(
            {
                "emotion": {"user_emotion": "lonely", "support_needed": True},
                "turn_judgement": {
                    "relationship_delta": {"label": "靠近"},
                    "memory_candidate": {"save": True, "memory_scope": "mid"},
                    "risk_signal": {"level": "none"},
                    "response_mode": "lonely_support",
                },
            }
        )

        self.assertIn("【本轮判断】", prompt)
        self.assertIn("孤独陪伴", prompt)

    def test_runtime_prompt_includes_few_shot_examples(self):
        prompt = build_runtime_system_prompt({})

        self.assertIn("## 对话示范", prompt)
        self.assertIn("用户表达过度依赖", prompt)

    def test_save_memory_tool_is_registered(self):
        self.assertIn("save_memory_tool", [item.name for item in tools])

    def test_merge_similar_memories_tool_is_registered(self):
        self.assertIn("merge_similar_memories_tool", [item.name for item in tools])

    def test_trim_short_term_messages_drops_orphan_tool_messages(self):
        messages = [
            ToolMessage(content="orphan result", tool_call_id="call-orphan"),
            HumanMessage(content="latest"),
        ]

        trimmed = trim_short_term_messages(messages)

        self.assertEqual(len(trimmed), 1)
        self.assertEqual(trimmed[0].type, "human")

    def test_trim_short_term_messages_preserves_complete_tool_blocks(self):
        messages = [HumanMessage(content=f"old-{index}") for index in range(30)]
        messages.extend(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_memory_tool",
                            "args": {"query": "memory"},
                            "id": "call-memory",
                        }
                    ],
                ),
                ToolMessage(content="memory result", tool_call_id="call-memory"),
                HumanMessage(content="latest"),
            ]
        )

        trimmed = trim_short_term_messages(messages)

        self.assertLessEqual(len(trimmed), 24)
        self.assertEqual(trimmed[-3].type, "ai")
        self.assertTrue(trimmed[-3].tool_calls)
        self.assertEqual(trimmed[-2].type, "tool")
        self.assertEqual(trimmed[-2].tool_call_id, "call-memory")
        self.assertEqual(trimmed[-1].type, "human")


if __name__ == "__main__":
    unittest.main()
