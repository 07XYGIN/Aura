import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.agent.tools.memory import merge_similar_memories_tool, save_memory_tool


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


class MergeSimilarMemoriesToolTest(unittest.TestCase):
    def test_merge_similar_memories_tool_requires_user_id(self):
        with patch("app.core.agent.tools.memory.list_memory_merge_candidates") as list_candidates:
            result = merge_similar_memories_tool.invoke({})

        self.assertIn("缺少用户 ID", result)
        list_candidates.assert_not_called()

    def test_merge_similar_memories_tool_returns_when_no_candidates(self):
        with patch(
            "app.core.agent.tools.memory.list_memory_merge_candidates",
            return_value={"items": [], "total": 0, "threshold": 0.9, "scanned": 5},
        ) as list_candidates:
            result = merge_similar_memories_tool.invoke(
                {"threshold": 0.9, "limit": 1, "scan_limit": 80},
                config={"configurable": {"user_id": "user-1"}},
            )

        self.assertIn("没有发现需要合并", result)
        list_candidates.assert_called_once_with(
            user_id="user-1",
            threshold=0.9,
            limit=1,
            scan_limit=80,
        )

    def test_merge_similar_memories_tool_applies_first_candidate(self):
        candidate = {
            "memory_keys": ["key-a", "key-b"],
            "suggested_title": "火锅偏好",
            "suggested_content": "喜欢和朋友吃火锅，但不太能吃辣。",
            "suggested_reason": "内容重复且互补",
        }
        with (
            patch(
                "app.core.agent.tools.memory.list_memory_merge_candidates",
                return_value={"items": [candidate], "total": 1, "threshold": 0.88, "scanned": 20},
            ) as list_candidates,
            patch(
                "app.core.agent.tools.memory.apply_memory_merge",
                return_value={
                    "memory_key": "merged-key",
                    "merged_from": ["key-a", "key-b"],
                    "title": "火锅偏好",
                    "content": "喜欢和朋友吃火锅，但不太能吃辣。",
                    "reason": "整理重复记忆",
                },
            ) as apply_merge,
        ):
            result = merge_similar_memories_tool.invoke(
                {"threshold": 0.7, "limit": 5, "scan_limit": 999, "reason": "整理重复记忆"},
                config={"configurable": {"user_id": "user-1"}},
            )

        self.assertIn("已合并 1 组相似长期记忆", result)
        self.assertIn("合并前的旧记忆已标记为已替代", result)
        list_candidates.assert_called_once_with(
            user_id="user-1",
            threshold=0.8,
            limit=3,
            scan_limit=500,
        )
        apply_merge.assert_called_once_with(
            user_id="user-1",
            memory_keys=["key-a", "key-b"],
            merged_title="火锅偏好",
            merged_content="喜欢和朋友吃火锅，但不太能吃辣。",
            reason="整理重复记忆",
            source="memory_merge_tool",
        )

    def test_merge_similar_memories_tool_topic_mode_requires_topic(self):
        with patch("app.core.agent.tools.memory.list_topic_memory_merge_candidates") as list_candidates:
            result = merge_similar_memories_tool.invoke(
                {"mode": "topic"},
                config={"configurable": {"user_id": "user-1"}},
            )

        self.assertIn("缺少明确整理主题", result)
        list_candidates.assert_not_called()

    def test_merge_similar_memories_tool_topic_mode_applies_candidate(self):
        candidate = {
            "memory_keys": ["key-a", "key-b", "key-c"],
            "suggested_title": "Aura 项目改动",
            "suggested_content": "今天集中折腾 Aura 项目，提到人设、情绪检测和模型采购相关改动。",
            "suggested_reason": "同一主题下的项目迭代线索",
        }
        with (
            patch(
                "app.core.agent.tools.memory.list_topic_memory_merge_candidates",
                return_value={"items": [candidate], "total": 1, "threshold": 0.52, "scanned": 8},
            ) as list_candidates,
            patch(
                "app.core.agent.tools.memory.apply_memory_merge",
                return_value={
                    "memory_key": "merged-key",
                    "merged_from": ["key-a", "key-b", "key-c"],
                    "title": "Aura 项目改动",
                    "content": "今天集中折腾 Aura 项目，提到人设、情绪检测和模型采购相关改动。",
                    "reason": "按主题整理",
                },
            ) as apply_merge,
        ):
            result = merge_similar_memories_tool.invoke(
                {
                    "mode": "topic",
                    "topic": "今天 Aura 项目改动",
                    "threshold": 0.2,
                    "limit": 9,
                    "scan_limit": 999,
                    "reason": "按主题整理",
                },
                config={"configurable": {"user_id": "user-1"}},
            )

        self.assertIn("已合并 1 组同主题长期记忆", result)
        list_candidates.assert_called_once_with(
            user_id="user-1",
            topic_query="今天 Aura 项目改动",
            threshold=0.35,
            limit=3,
            scan_limit=80,
        )
        apply_merge.assert_called_once_with(
            user_id="user-1",
            memory_keys=["key-a", "key-b", "key-c"],
            merged_title="Aura 项目改动",
            merged_content="今天集中折腾 Aura 项目，提到人设、情绪检测和模型采购相关改动。",
            reason="按主题整理",
            source="memory_merge_tool",
        )

    def test_merge_similar_memories_tool_topic_mode_defaults_to_topic_threshold(self):
        with (
            patch(
                "app.core.agent.tools.memory.list_topic_memory_merge_candidates",
                return_value={"items": [], "total": 0, "threshold": 0.52, "scanned": 0},
            ) as list_candidates,
            patch("app.core.agent.tools.memory.apply_memory_merge") as apply_merge,
        ):
            result = merge_similar_memories_tool.invoke(
                {"mode": "topic", "topic": "今天 Aura 项目改动"},
                config={"configurable": {"user_id": "user-1"}},
            )

        self.assertIn("没有发现足够归并", result)
        list_candidates.assert_called_once_with(
            user_id="user-1",
            topic_query="今天 Aura 项目改动",
            threshold=0.52,
            limit=1,
            scan_limit=20,
        )
        apply_merge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
