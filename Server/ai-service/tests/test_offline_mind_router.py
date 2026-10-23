from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.routers.offline_mind import read_sleep_cycles, read_thought_seeds


class OfflineMindRouterTest(unittest.IsolatedAsyncioTestCase):
    """验证离线心智查询始终绑定 JWT 用户。"""

    async def test_thought_list_uses_authenticated_user(self) -> None:
        session = object()
        with patch(
            "app.routers.offline_mind.list_thought_seeds_async",
            AsyncMock(return_value=[{"status": "cancelled"}]),
        ) as service:
            response = await read_thought_seeds(
                current_user_id="authenticated-user",
                session=session,
                status="cancelled",
                limit=20,
            )

        service.assert_awaited_once_with(
            session,
            "authenticated-user",
            status="cancelled",
            limit=20,
        )
        self.assertEqual(response.data, {"items": [{"status": "cancelled"}]})

    async def test_sleep_cycle_list_uses_authenticated_user(self) -> None:
        session = object()
        with patch(
            "app.routers.offline_mind.list_sleep_cycles_async",
            AsyncMock(return_value=[{"localDate": "2026-07-22"}]),
        ) as service:
            response = await read_sleep_cycles(
                current_user_id="authenticated-user",
                session=session,
                limit=10,
            )

        service.assert_awaited_once_with(session, "authenticated-user", limit=10)
        self.assertEqual(response.data["items"][0]["localDate"], "2026-07-22")


if __name__ == "__main__":
    unittest.main()
