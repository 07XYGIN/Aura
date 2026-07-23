from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.core.games.bash.service import BashGameServiceError
from app.routers.games import create_bash_game
from app.schemas.game import BashGameStartRequest


class BashRouterTest(unittest.IsolatedAsyncioTestCase):
    """验证巴什 HTTP 路由正确传递认证用户并映射领域错误。"""

    async def test_create_route_uses_authenticated_user(self) -> None:
        """路由应把 JWT 用户 ID 和原始请求交给服务并包装成功响应。"""

        request = BashGameStartRequest(startRequestId="route-start")
        expected = {"action": "started", "game": {"id": "game-1"}}
        fake_session = object()
        with patch(
            "app.routers.games.start_bash_game",
            new=AsyncMock(return_value=expected),
        ) as start:
            response = await create_bash_game(request, "user-from-jwt", fake_session)

        self.assertEqual(response.data, expected)
        start.assert_awaited_once_with(fake_session, "user-from-jwt", request)

    async def test_create_route_preserves_service_status_code(self) -> None:
        """领域层 409 冲突应转换为同状态码和中文详情的 HTTPException。"""

        request = BashGameStartRequest(startRequestId="route-conflict")
        with patch(
            "app.routers.games.start_bash_game",
            new=AsyncMock(
                side_effect=BashGameServiceError("已经有一局正在进行", status_code=409)
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await create_bash_game(request, "user-from-jwt", object())

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, "已经有一局正在进行")


if __name__ == "__main__":
    unittest.main()
