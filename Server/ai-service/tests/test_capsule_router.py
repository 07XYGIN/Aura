from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.routers.capsules import (
    create_capsule,
    read_capsules,
    report_github_event,
)
from app.schemas.capsule import (
    ConditionalMessageCreateRequest,
    GitHubEventRequest,
)


class ConditionalMessageRouterTest(unittest.IsolatedAsyncioTestCase):
    """验证路由始终使用 JWT 用户，并保持密封响应边界。"""

    async def test_create_route_uses_authenticated_user_and_hides_content(self) -> None:
        request = ConditionalMessageCreateRequest(
            messageType="time_capsule",
            conditionType="time",
            title="上线后打开",
            content="这是密封正文",
            deliverAt=datetime.now(UTC) + timedelta(days=1),
            clientRequestId="create-1",
        )
        sealed = {
            "id": "message-1",
            "title": "上线后打开",
            "content": None,
            "contentSealed": True,
            "status": "sealed",
        }
        with patch(
            "app.routers.capsules.create_conditional_message",
            AsyncMock(return_value=sealed),
        ) as service:
            response = await create_capsule(
                request,
                current_user_id="jwt-user",
                session=object(),
            )

        service.assert_awaited_once_with(service.await_args.args[0], "jwt-user", request)
        self.assertIsNone(response.data["content"])
        self.assertNotIn("这是密封正文", response.model_dump_json())

    async def test_list_route_is_scoped_to_authenticated_user(self) -> None:
        with patch(
            "app.routers.capsules.list_conditional_messages",
            AsyncMock(return_value=[]),
        ) as service:
            response = await read_capsules(
                current_user_id="jwt-user",
                session=object(),
                status="sealed",
                messageType="secret_vault",
                limit=20,
            )

        service.assert_awaited_once_with(
            service.await_args.args[0],
            "jwt-user",
            status="sealed",
            message_type="secret_vault",
            limit=20,
        )
        self.assertEqual(response.data, {"items": []})

    async def test_github_route_uses_delivery_id_and_not_payload_user(self) -> None:
        request = GitHubEventRequest(
            repository="07XYGIN/Aura",
            event="workflow_run",
            deliveryId="delivery-1",
            conclusion="success",
        )
        with patch(
            "app.routers.capsules.trigger_github_event_messages",
            AsyncMock(return_value=1),
        ) as service:
            response = await report_github_event(
                request,
                current_user_id="jwt-user",
                session=object(),
            )

        self.assertEqual(service.await_args.args[1], "jwt-user")
        self.assertEqual(service.await_args.kwargs["delivery_id"], "delivery-1")
        self.assertEqual(response.data, {"triggeredCount": 1})


if __name__ == "__main__":
    unittest.main()
