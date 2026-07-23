from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.core.pet.chat import PetChatResponse
from app.routers.msg import pet_event_generator


class PetSseTest(unittest.IsolatedAsyncioTestCase):
    """验证宠物状态、Aura 文本和 SSE 终止帧的顺序与幂等性。"""

    async def test_pet_stream_emits_state_content_and_done(self) -> None:
        """历史不可用时应降级为 content，同时保留宠物状态事件。"""

        response = PetChatResponse(
            action="feed",
            snapshot={
                "action": "feed",
                "idempotentReplay": False,
                "pet": {"id": "pet-1", "version": 2},
                "event": {"narrative": "团子吃饱了。"},
            },
            messages=["团子吃饱了。"],
        )
        with patch("app.routers.msg.append_external_history_turn", return_value=None):
            frames = [
                frame
                async for frame in pet_event_generator(
                    response,
                    message="喂宠物",
                    user_id="user-1",
                    client_message_id="turn-feed",
                )
            ]
        state = json.loads(frames[0].removeprefix("data: ").strip())
        content = json.loads(frames[1].removeprefix("data: ").strip())
        self.assertEqual(state["event"], "pet_state")
        self.assertEqual(content["event"], "content")
        self.assertEqual(frames[-1], "data: [DONE]\n\n")

    async def test_idempotent_replay_does_not_duplicate_history(self) -> None:
        """宠物事件重放只返回 SSE，不再次追加 LangGraph 历史。"""

        response = PetChatResponse(
            action="action_replayed",
            snapshot={
                "action": "action_replayed",
                "idempotentReplay": True,
                "pet": {"id": "pet-1", "version": 2},
                "event": {"narrative": "团子已经吃过了。"},
            },
            messages=["这件事已经记下了，没有重复操作。"],
        )
        with patch("app.routers.msg.append_external_history_turn") as append_history:
            frames = [
                frame
                async for frame in pet_event_generator(
                    response,
                    message="喂宠物",
                    user_id="user-1",
                    client_message_id="same-turn",
                )
            ]
        append_history.assert_not_called()
        self.assertEqual(frames[-1], "data: [DONE]\n\n")


if __name__ == "__main__":
    unittest.main()
