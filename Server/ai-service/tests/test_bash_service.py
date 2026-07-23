from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import uuid4

from app.core.games.bash.service import (
    BashGameServiceError,
    ensure_active_version_and_turn,
    record_aura_move,
    record_move,
    resolve_first_player,
)


class BashServiceDomainTest(unittest.TestCase):
    """验证不依赖数据库 I/O 的事务服务领域步骤。"""

    def build_game(self, remaining: int = 15, current_player: str = "user"):
        """构造具备服务函数所需字段的轻量棋局对象。"""

        return SimpleNamespace(
            id=uuid4(),
            remaining_stones=remaining,
            max_take=3,
            difficulty="serious",
            status="active",
            winner=None,
            current_player=current_player,
            finished_at=None,
            version=0,
        )

    def test_record_user_move_updates_authoritative_state(self) -> None:
        """记录用户行动时应同时生成事件并把会话轮次切给 Aura。"""

        game = self.build_game()
        move = record_move(
            game,
            turn_no=1,
            player="user",
            take_count=3,
            client_move_id="move-1",
        )
        self.assertEqual(move.remaining_before, 15)
        self.assertEqual(move.remaining_after, 12)
        self.assertEqual(game.remaining_stones, 12)
        self.assertEqual(game.current_player, "aura")

    def test_record_last_move_finishes_game(self) -> None:
        """拿走最后一颗时应立即设置胜者、终局状态和结束时间。"""

        game = self.build_game(remaining=1)
        record_move(
            game,
            turn_no=3,
            player="user",
            take_count=1,
            client_move_id="move-win",
        )
        self.assertEqual(game.status, "finished")
        self.assertEqual(game.winner, "user")
        self.assertIsNone(game.current_player)
        self.assertIsNotNone(game.finished_at)

    def test_record_aura_move_uses_engine_strategy(self) -> None:
        """Aura 回合应通过纯引擎落子并把行动策略写入事件。"""

        game = self.build_game(remaining=14, current_player="aura")
        move = record_aura_move(game, turn_no=2)
        self.assertEqual(move.take_count, 2)
        self.assertEqual(move.strategy, "control")
        self.assertEqual(game.remaining_stones, 12)
        self.assertEqual(game.current_player, "user")

    def test_stale_version_and_wrong_turn_are_conflicts(self) -> None:
        """旧版本或错误玩家都必须在写事件前被拒绝。"""

        game = self.build_game()
        with self.assertRaises(BashGameServiceError) as stale:
            ensure_active_version_and_turn(game, 1, "user")
        self.assertEqual(stale.exception.status_code, 409)

        game.current_player = "aura"
        with self.assertRaises(BashGameServiceError) as wrong_turn:
            ensure_active_version_and_turn(game, 0, "user")
        self.assertEqual(wrong_turn.exception.status_code, 409)

    def test_random_first_player_is_stable(self) -> None:
        """相同开始请求 ID 的随机先手必须可复现。"""

        self.assertEqual(
            resolve_first_player("random", "request-1"),
            resolve_first_player("random", "request-1"),
        )


if __name__ == "__main__":
    unittest.main()
