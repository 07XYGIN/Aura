from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.core.pet.service import PetServiceError
from app.routers.pet import adopt_companion_pet
from app.schemas.pet import PetAdoptRequest


class PetRouterTest(unittest.IsolatedAsyncioTestCase):
    """验证宠物路由传递认证用户并保留领域错误状态码。"""

    async def test_adopt_route_uses_authenticated_user(self) -> None:
        """JWT 用户 ID 应作为唯一所有者传给领养服务。"""

        request = PetAdoptRequest(
            name="团子",
            species="cat",
            personality="gentle",
            adoptionRequestId="route-adopt",
        )
        expected = {"action": "adopted", "pet": {"id": "pet-1"}}
        fake_session = object()
        with patch("app.routers.pet.adopt_pet", new=AsyncMock(return_value=expected)) as adopt:
            response = await adopt_companion_pet(request, "user-from-jwt", fake_session)
        self.assertEqual(response.data, expected)
        adopt.assert_awaited_once_with(fake_session, "user-from-jwt", request)

    async def test_adopt_route_maps_conflict_to_http_409(self) -> None:
        """已经有宠物时应保留服务层 409 和中文消息。"""

        request = PetAdoptRequest(name="团子", adoptionRequestId="route-conflict")
        with patch(
            "app.routers.pet.adopt_pet",
            new=AsyncMock(side_effect=PetServiceError("已经领养宠物", status_code=409)),
        ):
            with self.assertRaises(HTTPException) as raised:
                await adopt_companion_pet(request, "user-from-jwt", object())
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, "已经领养宠物")


if __name__ == "__main__":
    unittest.main()
