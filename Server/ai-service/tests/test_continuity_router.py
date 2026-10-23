from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.core.continuity.service import RelationshipThreadServiceError
from app.routers.continuity import create_thread, transition_thread
from app.schemas.continuity import (
    RelationshipThreadCreateRequest,
    RelationshipThreadTransitionRequest,
)


class ContinuityRouterTest(unittest.IsolatedAsyncioTestCase):
    """验证连续性 HTTP 路由只使用 JWT 身份并保留领域状态码。"""

    async def test_create_route_uses_authenticated_user(self) -> None:
        user_id = str(uuid4())
        request = RelationshipThreadCreateRequest(
            threadType="open_item",
            title="发布接口",
            summary="明天发布接口",
            clientRequestId="create-1",
        )
        session = SimpleNamespace()
        snapshot = {"thread": {"id": str(uuid4())}}
        with patch(
            "app.routers.continuity.create_relationship_thread",
            AsyncMock(return_value=snapshot),
        ) as create:
            response = await create_thread(request, user_id, session)

        self.assertEqual(response.data, snapshot)
        create.assert_awaited_once_with(session, user_id, request)

    async def test_transition_route_preserves_conflict_status(self) -> None:
        request = RelationshipThreadTransitionRequest(
            action="resolve",
            clientActionId="resolve-1",
            expectedVersion=1,
        )
        with patch(
            "app.routers.continuity.transition_relationship_thread",
            AsyncMock(
                side_effect=RelationshipThreadServiceError(
                    "关系线程已经变化",
                    status_code=409,
                )
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await transition_thread(
                    str(uuid4()),
                    request,
                    str(uuid4()),
                    SimpleNamespace(),
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, "关系线程已经变化")


if __name__ == "__main__":
    unittest.main()
