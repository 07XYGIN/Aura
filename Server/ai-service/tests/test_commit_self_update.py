from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "record_self_update_from_commit.py"
SPEC = importlib.util.spec_from_file_location("record_self_update_from_commit", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CommitSelfUpdateTests(unittest.TestCase):
    def test_live2d_commit_uses_appearance_context(self):
        commit = MODULE.CommitInfo(
            sha="a" * 40,
            short_sha="abcdef1",
            subject="增加 Live2D 聊天形象",
            body="",
            changed_paths=("AI-Web/apps/web/components/arua/live2d-stage.tsx",),
        )

        update = MODULE.build_self_update(commit)

        self.assertEqual(update.category, "appearance")
        self.assertEqual(update.title, "增加 Live2D 聊天形象")
        self.assertIn("Live2D 形象", update.detail)
        self.assertEqual(update.metadata["source_commit"], "a" * 40)

    def test_prompt_change_prioritizes_personality_context(self):
        commit = MODULE.CommitInfo(
            sha="b" * 40,
            short_sha="bcdef12",
            subject="调整 Aura 的日常聊天语气",
            body="不再强行分析用户的无聊。",
            changed_paths=("Server/ai-service/app/core/agent/prompt.py",),
        )

        update = MODULE.build_self_update(commit)

        self.assertEqual(update.category, "personality")
        self.assertIn("对话设定", update.detail)
        self.assertIn("不再强行分析用户的无聊", update.detail)


if __name__ == "__main__":
    unittest.main()
