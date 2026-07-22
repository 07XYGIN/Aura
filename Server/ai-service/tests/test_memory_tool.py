import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.tools.memory import save_memory_tool
from app.core.memory.maintenance import merge_memories


class SaveMemoryToolTest(unittest.TestCase):
    def test_save_memory_tool_uses_config_user(self):
        with patch("app.core.agent.tools.memory.save_memory", return_value="memory-key") as save_memory:
            result = save_memory_tool.invoke(
                {
                    "title": "饮食偏好",
                    "content": "用户明确说自己不太能吃辣。",
                    "memory_scope": "long",
                    "confidence": 0.92,
                    "reason": "用户明确要求记住",
                    "signals": ["explicit_request", "preference"],
                },
                config={"configurable": {"user_id": "user-1"}},
            )

        self.assertEqual(result, "已保存长期记忆：饮食偏好。")
        save_memory.assert_called_once()
        _, kwargs = save_memory.call_args
        self.assertEqual(kwargs["user_id"], "user-1")
        self.assertEqual(kwargs["memory_scope"], "long")
        self.assertEqual(kwargs["extra_metadata"]["reason"], "用户明确要求记住")

    def test_save_memory_tool_requires_user_id(self):
        with patch("app.core.agent.tools.memory.save_memory") as save_memory:
            result = save_memory_tool.invoke(
                {"title": "饮食偏好", "content": "不太能吃辣。", "memory_scope": "long"}
            )

        self.assertIn("缺少用户 ID", result)
        save_memory.assert_not_called()


class MemoryMaintenanceTest(unittest.TestCase):
    def test_merge_memories_is_plain_background_function(self):
        candidate = {
            "memory_keys": ["key-a", "key-b"],
            "suggested_title": "饮食偏好",
            "suggested_content": "喜欢火锅，但不太能吃辣。",
        }
        with (
            patch(
                "app.core.memory.maintenance.list_memory_merge_candidates",
                return_value={"items": [candidate]},
            ),
            patch(
                "app.core.memory.maintenance.apply_memory_merge",
                return_value={"memory_key": "merged-key", "title": "饮食偏好"},
            ) as apply_merge,
        ):
            result = merge_memories("user-1", reason="后台整理")

        self.assertEqual(result["mergedCount"], 1)
        apply_merge.assert_called_once_with(
            user_id="user-1",
            memory_keys=["key-a", "key-b"],
            merged_title="饮食偏好",
            merged_content="喜欢火锅，但不太能吃辣。",
            reason="后台整理",
            source="memory_maintenance",
        )

    def test_topic_merge_requires_topic(self):
        with self.assertRaisesRegex(ValueError, "必须提供明确主题"):
            merge_memories("user-1", mode="topic")


if __name__ == "__main__":
    unittest.main()
