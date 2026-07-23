from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.core.pet.chat import try_handle_pet_chat_message
from app.core.pet.service import PetServiceError


class PetChatTest(unittest.IsolatedAsyncioTestCase):
    """验证宠物聊天分流只处理明确命令并传递幂等参数。"""

    async def test_ordinary_chat_returns_none_without_database_query(self) -> None:
        """没有宠物标记的普通亲密对话不能触发宠物状态查询。"""

        with patch("app.core.pet.chat.get_pet_for_user", new=AsyncMock()) as get_pet:
            response = await try_handle_pet_chat_message(
                SimpleNamespace(),
                message="今天写代码有点累",
                user_id="not-a-uuid",
                client_message_id="turn-ordinary",
            )
        self.assertIsNone(response)
        get_pet.assert_not_awaited()

    async def test_romantic_hug_is_not_intercepted_as_pet_action(self) -> None:
        """即使已经有宠物，“宝宝抱抱”也应继续交给情侣主对话。"""

        pet = SimpleNamespace(id=uuid4(), version=1, name="团子")
        with patch("app.core.pet.chat.get_pet_for_user", new=AsyncMock(return_value=pet)):
            response = await try_handle_pet_chat_message(
                SimpleNamespace(),
                message="宝宝抱抱",
                user_id=str(uuid4()),
                client_message_id="turn-hug",
            )
        self.assertIsNone(response)

    async def test_adoption_command_calls_service_with_client_turn_id(self) -> None:
        """明确领养命令应把客户端回合 ID 作为领养幂等键。"""

        snapshot = {
            "action": "adopted",
            "idempotentReplay": False,
            "pet": {"id": str(uuid4()), "name": "团子", "version": 1},
            "event": {"narrative": "我们把小猫团子接回来了。"},
            "recentEvents": [],
            "statusText": "团子现在很放松。",
        }
        with (
            patch("app.core.pet.chat.get_pet_for_user", new=AsyncMock(return_value=None)),
            patch("app.core.pet.chat.adopt_pet", new=AsyncMock(return_value=snapshot)) as adopt,
        ):
            response = await try_handle_pet_chat_message(
                SimpleNamespace(),
                message="我们领养一只猫，叫团子",
                user_id=str(uuid4()),
                client_message_id="turn-adopt",
            )
        request = adopt.await_args.args[2]
        self.assertEqual(request.name, "团子")
        self.assertEqual(request.species, "cat")
        self.assertEqual(request.adoption_request_id, "turn-adopt")
        self.assertEqual(response.action, "adopted")

    async def test_care_command_uses_current_pet_version(self) -> None:
        """聊天照顾动作应携带当前版本和客户端动作 ID。"""

        pet = SimpleNamespace(id=uuid4(), version=7, name="团子")
        snapshot = {
            "action": "feed",
            "idempotentReplay": False,
            "pet": {"id": str(pet.id), "name": "团子", "version": 8},
            "event": {"narrative": "团子认真吃了一会儿。"},
            "recentEvents": [],
            "statusText": "团子吃饱了。",
        }
        with (
            patch("app.core.pet.chat.get_pet_for_user", new=AsyncMock(return_value=pet)),
            patch("app.core.pet.chat.perform_pet_action", new=AsyncMock(return_value=snapshot)) as care,
        ):
            response = await try_handle_pet_chat_message(
                SimpleNamespace(),
                message="给宠物喂点东西",
                user_id=str(uuid4()),
                client_message_id="turn-feed",
            )
        request = care.await_args.args[2]
        self.assertEqual(request.action, "feed")
        self.assertEqual(request.expected_version, 7)
        self.assertEqual(request.client_action_id, "turn-feed")
        self.assertEqual(response.action, "feed")

    async def test_status_command_uses_lazy_settlement_service(self) -> None:
        """查看宠物必须经过锁定结算服务，不能直接序列化过期 ORM 状态。"""

        pet = SimpleNamespace(id=uuid4(), version=3, name="团子")
        snapshot = {
            "action": "settled",
            "idempotentReplay": False,
            "pet": {"id": str(pet.id), "name": "团子", "version": 4},
            "event": None,
            "recentEvents": [],
            "statusText": "团子现在吃得很饱，精神很好。",
        }
        with (
            patch("app.core.pet.chat.get_pet_for_user", new=AsyncMock(return_value=pet)),
            patch("app.core.pet.chat.get_pet_snapshot", new=AsyncMock(return_value=snapshot)) as get_snapshot,
        ):
            response = await try_handle_pet_chat_message(
                SimpleNamespace(),
                message="看看宠物怎么样",
                user_id=str(uuid4()),
                client_message_id="turn-status",
            )

        get_snapshot.assert_awaited_once()
        self.assertEqual(response.snapshot["pet"]["version"], 4)

    async def test_pet_write_command_requires_stable_client_message_id(self) -> None:
        """没有 clientMessageId 时不得用随机键执行不可安全重试的照顾动作。"""

        pet = SimpleNamespace(id=uuid4(), version=1, name="团子")
        with patch("app.core.pet.chat.get_pet_for_user", new=AsyncMock(return_value=pet)):
            with self.assertRaises(PetServiceError) as raised:
                await try_handle_pet_chat_message(
                    SimpleNamespace(),
                    message="给宠物喂点东西",
                    user_id=str(uuid4()),
                    client_message_id=None,
                )
        self.assertIn("clientMessageId", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
