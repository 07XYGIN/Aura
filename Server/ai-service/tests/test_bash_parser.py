from __future__ import annotations

import unittest

from app.core.games.bash.parser import parse_bash_chat_intent


class BashParserTest(unittest.TestCase):
    """验证游戏命令只在高置信度场景命中。"""

    def test_explicit_bash_name_starts_game(self) -> None:
        """明确提到巴什博弈时，无活动棋局也应识别开局。"""

        intent = parse_bash_chat_intent("我们来一局巴什博弈", has_active_game=False)
        self.assertEqual(intent.action, "start")

    def test_rules_are_detected_without_starting_game(self) -> None:
        """询问巴什规则时应返回 rules，而不是直接创建棋局。"""

        intent = parse_bash_chat_intent("巴什博弈怎么玩？规则是什么", has_active_game=False)
        self.assertEqual(intent.action, "rules")

    def test_move_requires_active_game(self) -> None:
        """“我拿两个”只有在活动棋局中才是取子命令。"""

        self.assertIsNone(parse_bash_chat_intent("我拿两个", has_active_game=False))
        intent = parse_bash_chat_intent("我拿两个", has_active_game=True)
        self.assertEqual(intent.action, "move")
        self.assertEqual(intent.take_count, 2)

    def test_bare_number_requires_active_game(self) -> None:
        """活动棋局中的裸数字可以快速落子，普通聊天中不得截获。"""

        self.assertIsNone(parse_bash_chat_intent("3", has_active_game=False))
        self.assertEqual(parse_bash_chat_intent("3", has_active_game=True).take_count, 3)

    def test_ordinary_sentence_is_not_misclassified_as_move(self) -> None:
        """“拿三个方案”这类普通表达即使有活动棋局也必须交给主聊天。"""

        self.assertIsNone(parse_bash_chat_intent("我拿三个方案比较一下", has_active_game=True))

    def test_active_game_commands_cover_status_and_resign(self) -> None:
        """进行中棋局应识别状态查询与认输命令。"""

        self.assertEqual(
            parse_bash_chat_intent("还剩多少", has_active_game=True).action,
            "status",
        )
        self.assertEqual(
            parse_bash_chat_intent("不玩了，我认输", has_active_game=True).action,
            "resign",
        )


if __name__ == "__main__":
    unittest.main()
