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
    call_model,
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

    def test_runtime_prompt_includes_continuity_state_after_pet_context(self):
        prompt = build_runtime_system_prompt(
            {
                "pet_context": "【共同宠物】\n今天有一条真实宠物事件。",
                "continuity_state_context": "【连续状态】\n今天在家里书桌画草图。",
            }
        )

        self.assertIn("【连续状态】", prompt)
        self.assertGreater(prompt.find("【连续状态】"), prompt.find("【共同宠物】"))

    def test_runtime_prompt_includes_few_shot_examples(self):
        prompt = build_runtime_system_prompt({})

        self.assertIn("## 对话示范", prompt)
        self.assertIn("用户表达过度依赖", prompt)

    def test_output_format_instruction_comes_after_examples_and_runtime_context(self):
        prompt = build_runtime_system_prompt({})

        format_position = prompt.rfind("## 输出格式：多条独立消息")
        self.assertGreater(format_position, prompt.find("## 对话示范"))
        self.assertGreater(format_position, prompt.find("【本轮附件】"))
        self.assertIn('"itemUsages":[]', prompt)

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
        fake_aura = SimpleNamespace(
            update_state=unittest.mock.Mock(),
            get_state=unittest.mock.Mock(return_value=SimpleNamespace(values={})),
        )
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

    def test_append_proactive_history_message_replays_stable_id_without_duplicate(self):
        message_id = "stable-delivery-1"
        fake_aura = SimpleNamespace(update_state=unittest.mock.Mock())
        with (
            patch("app.core.agent.agent_graph.aura", fake_aura),
            patch(
                "app.core.agent.agent_graph.get_history",
                return_value=[
                    {
                        "id": f"ai-proactive-{message_id}",
                        "role": "aura",
                        "content": "已经发过",
                        "isProactive": True,
                    }
                ],
            ),
        ):
            appended = append_proactive_history_message(
                user_id="user-1",
                content="已经发过",
                message_id=message_id,
                sent_at=datetime.now(UTC),
            )

        self.assertTrue(appended)
        fake_aura.update_state.assert_not_called()

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

    def test_call_model_preserves_valid_relationship_action_sidecar(self):
        response = AIMessage(
            content=(
                '{"messages":["你昨天那个接口后来通了吗？"],'
                '"threadActions":[{"threadRef":"T1","action":"follow_up"}]}'
            )
        )
        state = {
            "messages": [HumanMessage(content="早")],
            "turn_id": "turn-1",
            "user_id": "user-1",
            "request_started_at": datetime.now(UTC).isoformat(),
        }

        with (
            patch(
                "app.core.agent.agent_graph.llm_with_tools",
                SimpleNamespace(invoke=unittest.mock.Mock(return_value=response)),
            ),
            patch("app.core.agent.agent_graph.store_reply_timing_state", return_value=True),
        ):
            result = call_model(state)

        self.assertEqual(
            result["relationship_actions"],
            {
                "turn_id": "turn-1",
                "items": [{"thread_ref": "T1", "action": "follow_up"}],
            },
        )

    def test_call_model_preserves_valid_relationship_item_usage_sidecar(self):
        response = AIMessage(
            content=(
                '{"messages":["宝宝，过来。"],'
                '"itemUsages":[{"itemRef":"K1"}]}'
            )
        )
        state = {
            "messages": [HumanMessage(content="要抱抱")],
            "turn_id": "turn-knowledge-1",
            "user_id": "user-1",
            "request_started_at": datetime.now(UTC).isoformat(),
        }

        with (
            patch(
                "app.core.agent.agent_graph.llm_with_tools",
                SimpleNamespace(invoke=unittest.mock.Mock(return_value=response)),
            ),
            patch("app.core.agent.agent_graph.store_reply_timing_state", return_value=True),
        ):
            result = call_model(state)

        self.assertEqual(
            result["relationship_item_usages"],
            {
                "turn_id": "turn-knowledge-1",
                "items": [{"item_ref": "K1"}],
            },
        )


if __name__ == "__main__":
    unittest.main()
