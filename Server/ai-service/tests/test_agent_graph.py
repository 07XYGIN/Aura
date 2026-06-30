import sys
import unittest
from pathlib import Path

from langgraph.graph import END

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.agent_graph import build_runtime_system_prompt, should_continue, turn_judge


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


if __name__ == "__main__":
    unittest.main()
