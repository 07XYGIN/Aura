from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.schemas.request import MessageRequest
from main import create_app


class ProductSurfaceTests(unittest.IsolatedAsyncioTestCase):
    def test_optional_activity_routes_are_hidden_by_default(self) -> None:
        paths = set(create_app().openapi()["paths"])

        self.assertIn("/api/send/sse/", paths)
        self.assertIn("/api/memory/list", paths)
        self.assertIn("/api/continuity/chapters", paths)
        self.assertNotIn("/api/games/bash", paths)
        self.assertNotIn("/api/pet", paths)
        self.assertNotIn("/api/continuity/capsules", paths)

    async def test_optional_activity_commands_fall_through_to_normal_chat(self) -> None:
        from app.routers import msg

        user_id = str(uuid4())
        request = MessageRequest(message="来一局巴什博弈", userId=user_id)

        with (
            patch.object(msg, "AURA_OPTIONAL_ACTIVITIES_ENABLED", False),
            patch.object(msg, "try_handle_focus_chat_message", new=AsyncMock()) as focus,
            patch.object(msg, "try_handle_bash_chat_message", new=AsyncMock()) as game,
            patch.object(msg, "try_handle_pet_chat_message", new=AsyncMock()) as pet,
            patch.object(msg, "_try_acquire_sse_slot", return_value=True),
            patch.object(msg, "schedule_user_message_activity_record"),
        ):
            response = await msg.send_message(request, user_id)

        self.assertEqual(response.media_type, "text/event-stream")
        focus.assert_not_awaited()
        game.assert_not_awaited()
        pet.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
