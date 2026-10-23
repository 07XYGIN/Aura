from __future__ import annotations

import unittest
from unittest.mock import patch

from app.routers.continuity_state import read_current_continuity_state


class ContinuityStateRouterTest(unittest.IsolatedAsyncioTestCase):
    """验证状态接口使用 JWT 用户并隐藏内部 prompt。"""

    async def test_current_state_uses_authenticated_user(self) -> None:
        loaded = {
            "daily_state": {"activity": "画草图"},
            "emotional_afterglow": {"emotion": "happy"},
            "active_scene": {"place": "阳台"},
            "prompt_context": "内部提示词不应返回",
        }
        with patch(
            "app.routers.continuity_state.load_continuity_state_context_sync",
            return_value=loaded,
        ) as service:
            response = await read_current_continuity_state("authenticated-user")

        service.assert_called_once_with("authenticated-user")
        self.assertEqual(response.data["dailyState"], {"activity": "画草图"})
        self.assertNotIn("prompt_context", response.data)


if __name__ == "__main__":
    unittest.main()
