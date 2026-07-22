import sys
import unittest
from pathlib import Path
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.agent_graph import (
    append_proactive_history_message,
    build_runtime_system_prompt,
    should_continue,
    tools,
    trim_short_term_messages,
    turn_judge,
)
from app.core.agent.self_changelog import format_self_changelog_context


class AgentGraphTest(unittest.TestCase):
    def test_should_continue_ends_when_history_is_empty(self):
        self.assertEqual(should_continue({"messages": []}), END)

    def test_should_continue_ends_when_messages_missing(self):
        self.assertEqual(should_continue({}), END)

    def test_turn_judge_uses_precomputed_judgement(self):
        judgement = {
            "emotion": {"user_emotion": "lonely", "support_needed": True},
            "interaction": {"mode": "affection", "target": "aura"},
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
                    "interaction": {"mode": "affection", "target": "aura"},
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

    def test_output_format_instruction_comes_after_examples_and_runtime_context(self):
        prompt = build_runtime_system_prompt({})

        format_position = prompt.rfind("## 输出格式：多条独立消息")
        self.assertGreater(format_position, prompt.find("## 对话示范"))
        self.assertGreater(format_position, prompt.find("【本轮附件】"))

    def test_self_changelog_context_uses_the_same_current_user_identity(self):
        entry = SimpleNamespace(
            category="persona",
            occurred_at=datetime(2026, 7, 22, tzinfo=UTC),
            change_date=None,
            title="统一用户身份",
            detail=None,
        )

        context = format_self_changelog_context([entry])

        self.assertIn("当前对话者就是小乔", context)
        self.assertIn("唯一的用户、创造者和维护者", context)
        self.assertNotIn("下面是 q ", context)

    def test_save_memory_tool_is_registered(self):
        self.assertIn("save_memory_tool", [item.name for item in tools])

    def test_chat_tool_registry_only_contains_runtime_tools(self):
        self.assertEqual(
            ["search_memory_tool", "save_memory_tool", "get_weather"],
            [item.name for item in tools],
        )

    def test_runtime_prompt_does_not_advertise_removed_pseudo_tools(self):
        prompt = build_runtime_system_prompt({})

        self.assertNotIn("get_emotional_support_advice", prompt)
        self.assertNotIn("get_relationship_status", prompt)
        self.assertNotIn("plan_daily_greetings", prompt)
        self.assertNotIn("merge_similar_memories_tool", prompt)

    def test_append_proactive_history_message_updates_graph_state(self):
        fake_aura = SimpleNamespace(update_state=unittest.mock.Mock())
        sent_at = datetime(2026, 7, 7, 10, 0, tzinfo=UTC)

        with patch("app.core.agent.agent_graph.aura", fake_aura):
            appended = append_proactive_history_message(
                user_id="user-1",
                content="我在。",
                message_id="msg-1",
                sent_at=sent_at,
                trigger_type="silence",
            )

        self.assertTrue(appended)
        config, state = fake_aura.update_state.call_args.args
        self.assertEqual(config["configurable"]["thread_id"], "user-1")
        message = state["messages"][0]
        self.assertEqual(message.type, "ai")
        self.assertEqual(message.content, "我在。")
        self.assertTrue(message.additional_kwargs["is_proactive"])
        self.assertEqual(message.additional_kwargs["trigger_type"], "silence")

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
