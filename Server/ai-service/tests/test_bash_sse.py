from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.core.games.bash.chat import BashChatResponse
from app.routers.msg import bash_game_event_generator


class BashSseTest(unittest.IsolatedAsyncioTestCase):
    """验证游戏 SSE 的状态、文本和终止帧顺序。"""

    async def test_game_stream_emits_state_content_and_done(self) -> None:
        """历史不可用时应降级为 content，且仍以 DONE 正常结束。"""

        response = BashChatResponse(
            action="started",
            snapshot={
                "action": "started",
                "game": {"id": "game-1", "version": 0},
                "newMoves": [],
                "recentMoves": [],
            },
            messages=["来，轮到你。"],
        )
        frames: list[str] = []
        with patch("app.routers.msg.append_external_history_turn", return_value=None):
            async for frame in bash_game_event_generator(
                response,
                message="来一局",
                user_id="user-1",
                client_message_id="turn-1",
            ):
                frames.append(frame)

        state = json.loads(frames[0].removeprefix("data: ").strip())
        content = json.loads(frames[1].removeprefix("data: ").strip())
        self.assertEqual(state["event"], "bash_game_state")
        self.assertEqual(content["event"], "content")
        self.assertEqual(frames[-1], "data: [DONE]\n\n")

    async def test_idempotent_replay_does_not_append_duplicate_history(self) -> None:
        """数据库幂等重放只返回 SSE，不应再次向 LangGraph 追加相同回合。"""

        response = BashChatResponse(
            action="move_replayed",
            snapshot={
                "action": "move_replayed",
                "idempotentReplay": True,
                "game": {"id": "game-1", "version": 1},
                "newMoves": [],
                "recentMoves": [],
            },
            messages=["这一步我已经记下了。"],
        )
        with patch("app.routers.msg.append_external_history_turn") as append_history:
            frames = [
                frame
                async for frame in bash_game_event_generator(
                    response,
                    message="我拿两颗",
                    user_id="user-1",
                    client_message_id="same-turn",
                )
            ]

        append_history.assert_not_called()
        content = json.loads(frames[1].removeprefix("data: ").strip())
        self.assertEqual(content["content"], "这一步我已经记下了。")
        self.assertEqual(frames[-1], "data: [DONE]\n\n")


if __name__ == "__main__":
    unittest.main()
