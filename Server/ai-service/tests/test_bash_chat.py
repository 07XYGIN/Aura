from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.core.games.bash.chat import try_handle_bash_chat_message


class BashChatTest(unittest.IsolatedAsyncioTestCase):
    """验证巴什聊天分流不会吞掉普通对话，并正确调用领域服务。"""

    async def test_ordinary_chat_returns_none_without_database_query(self) -> None:
        """完全不像游戏命令的文本应立即返回，不查询活动棋局。"""

        with patch("app.core.games.bash.chat.get_active_bash_game", new=AsyncMock()) as active:
            response = await try_handle_bash_chat_message(
                SimpleNamespace(),
                message="今天写代码有点累",
                user_id="not-even-a-uuid",
                client_message_id="turn-1",
            )
        self.assertIsNone(response)
        active.assert_not_awaited()

    async def test_start_command_calls_start_service(self) -> None:
        """明确开局命令应使用客户端回合 ID 作为幂等开始 ID。"""

        snapshot = {
            "action": "started",
            "idempotentReplay": False,
            "game": {
                "id": str(uuid4()),
                "initialStones": 15,
                "remainingStones": 15,
                "maxTake": 3,
                "firstPlayer": "user",
                "currentPlayer": "user",
                "difficulty": "serious",
                "status": "active",
                "winner": None,
                "version": 0,
            },
            "newMoves": [],
            "recentMoves": [],
        }
        with (
            patch("app.core.games.bash.chat.get_active_bash_game", new=AsyncMock(return_value=None)),
            patch("app.core.games.bash.chat.start_bash_game", new=AsyncMock(return_value=snapshot)) as start,
        ):
            response = await try_handle_bash_chat_message(
                SimpleNamespace(),
                message="来一局巴什博弈",
                user_id=str(uuid4()),
                client_message_id="turn-start",
            )
        self.assertEqual(response.action, "started")
        self.assertIn("你先", response.messages[0])
        self.assertEqual(start.await_args.args[2].start_request_id, "turn-start")

    async def test_move_command_uses_active_version(self) -> None:
        """聊天落子应携带活动棋局当前版本和客户端消息 ID。"""

        game = SimpleNamespace(id=uuid4(), version=4)
        snapshot = {
            "action": "moved",
            "idempotentReplay": False,
            "game": {
                "id": str(game.id),
                "remainingStones": 8,
                "maxTake": 3,
                "status": "active",
                "winner": None,
                "version": 5,
            },
            "newMoves": [
                {"player": "user", "takeCount": 2},
                {"player": "aura", "takeCount": 1},
            ],
            "recentMoves": [],
        }
        with (
            patch("app.core.games.bash.chat.get_active_bash_game", new=AsyncMock(return_value=game)),
            patch("app.core.games.bash.chat.perform_user_move", new=AsyncMock(return_value=snapshot)) as move,
        ):
            response = await try_handle_bash_chat_message(
                SimpleNamespace(),
                message="我拿两颗石子",
                user_id=str(uuid4()),
                client_message_id="turn-move",
            )
        request = move.await_args.args[3]
        self.assertEqual(request.take_count, 2)
        self.assertEqual(request.expected_version, 4)
        self.assertEqual(request.client_move_id, "turn-move")
        self.assertEqual(response.action, "moved")


if __name__ == "__main__":
    unittest.main()
