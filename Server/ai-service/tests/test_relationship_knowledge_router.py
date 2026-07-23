from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.core.continuity.knowledge import RelationshipKnowledgeServiceError
from app.routers.relationship_knowledge import (
    read_relationship_chapters,
    read_relationship_item,
    read_relationship_items,
)


class RelationshipKnowledgeRouterTest(unittest.IsolatedAsyncioTestCase):
    """验证关系知识接口始终使用 JWT 用户，并保留中文领域错误。"""

    async def test_item_list_uses_authenticated_user_and_filters(self) -> None:
        session = object()
        with patch(
            "app.routers.relationship_knowledge.list_relationship_items",
            AsyncMock(return_value=[{"id": "item-1"}]),
        ) as service:
            response = await read_relationship_items(
                current_user_id="authenticated-user",
                session=session,
                itemType="nickname",
                status="active",
                worldLayer="shared_history",
                limit=20,
            )

        service.assert_awaited_once_with(
            session,
            "authenticated-user",
            item_type="nickname",
            status="active",
            world_layer="shared_history",
            limit=20,
        )
        self.assertEqual(response.data, {"items": [{"id": "item-1"}]})

    async def test_item_detail_preserves_not_found_status(self) -> None:
        with patch(
            "app.routers.relationship_knowledge.get_relationship_item",
            AsyncMock(
                side_effect=RelationshipKnowledgeServiceError(
                    "关系物件不存在",
                    status_code=404,
                )
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await read_relationship_item(
                    item_id="missing",
                    current_user_id="authenticated-user",
                    session=object(),
                )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "关系物件不存在")

    async def test_chapter_list_uses_authenticated_user(self) -> None:
        session = object()
        with patch(
            "app.routers.relationship_knowledge.list_relationship_chapters",
            AsyncMock(return_value=[{"sequenceNo": 2}]),
        ) as service:
            response = await read_relationship_chapters(
                current_user_id="authenticated-user",
                session=session,
                limit=10,
            )

        service.assert_awaited_once_with(session, "authenticated-user", limit=10)
        self.assertEqual(response.data, {"items": [{"sequenceNo": 2}]})


if __name__ == "__main__":
    unittest.main()
