from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.schemas.request import MessageRequest
from main import create_app


class ProductSurfaceTests(unittest.IsolatedAsyncioTestCase):
    def test_removed_activity_routes_are_absent(self) -> None:
        paths = set(create_app().openapi()["paths"])

        self.assertIn("/api/send/sse/", paths)
        self.assertIn("/api/memory/list", paths)
        self.assertIn("/api/continuity/chapters", paths)
        self.assertNotIn("/api/games/bash", paths)
        self.assertNotIn("/api/pet", paths)
        self.assertIn("/api/continuity/capsules", paths)
        self.assertFalse(any(path.startswith("/api/focus") for path in paths))

    async def test_removed_activity_commands_fall_through_to_normal_chat(self) -> None:
        from app.routers import msg

        user_id = str(uuid4())
        request = MessageRequest(message="来一局巴什博弈", userId=user_id)

        with (
            patch.object(msg, "_try_acquire_sse_slot", return_value=True),
            patch.object(msg, "schedule_user_message_activity_record"),
        ):
            response = await msg.send_message(request, user_id)

        self.assertEqual(response.media_type, "text/event-stream")


if __name__ == "__main__":
    unittest.main()
