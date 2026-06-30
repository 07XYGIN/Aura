import sys
import unittest
from pathlib import Path

from langgraph.graph import END

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.agent_graph import should_continue


class AgentGraphTest(unittest.TestCase):
    def test_should_continue_ends_when_history_is_empty(self):
        self.assertEqual(should_continue({"messages": []}), END)

    def test_should_continue_ends_when_messages_missing(self):
        self.assertEqual(should_continue({}), END)


if __name__ == "__main__":
    unittest.main()
