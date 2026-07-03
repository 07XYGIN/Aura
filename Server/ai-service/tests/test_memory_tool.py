import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.tools.memory import save_memory_tool


class SaveMemoryToolTest(unittest.TestCase):
    def test_save_memory_tool_uses_config_user_and_saves_structured_memory(self):
        with patch("app.core.agent.tools.memory.save_memory", return_value="memory-key") as save_memory:
            result = save_memory_tool.invoke(
                {
                    "title": "饮食偏好",
                    "content": "用户喜欢番茄炒蛋。",
                    "memory_scope": "long",
                    "confidence": 0.92,
                    "reason": "用户明确要求记住",
                    "signals": ["explicit_request", "preference"],
                },
                config={"configurable": {"user_id": "user-1"}},
            )

        self.assertIn("已保存长期记忆", result)
        save_memory.assert_called_once()
        _, kwargs = save_memory.call_args
        self.assertEqual(kwargs["user_id"], "user-1")
        self.assertEqual(kwargs["title"], "饮食偏好")
        self.assertEqual(kwargs["content"], "用户喜欢番茄炒蛋。")
        self.assertEqual(kwargs["memory_scope"], "long")
        self.assertEqual(kwargs["confidence"], 0.92)
        self.assertEqual(kwargs["signals"], ["explicit_request", "preference"])
        self.assertEqual(kwargs["extra_metadata"]["source"], "save_memory_tool")
        self.assertEqual(kwargs["extra_metadata"]["reason"], "用户明确要求记住")

    def test_save_memory_tool_requires_user_id(self):
        with patch("app.core.agent.tools.memory.save_memory") as save_memory:
            result = save_memory_tool.invoke(
                {
                    "title": "饮食偏好",
                    "content": "用户喜欢番茄炒蛋。",
                    "memory_scope": "long",
                },
            )

        self.assertIn("缺少用户 ID", result)
        save_memory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
