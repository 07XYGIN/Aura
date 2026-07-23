from __future__ import annotations

import asyncio
import sys
import threading
import time
import unittest
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.routers import msg


class TestSseConcurrency(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_aura_agent = msg.aura_agent
        self.original_max_concurrency = msg._sse_max_concurrency
        self.original_queue_size = msg._sse_queue_size

    async def asyncTearDown(self) -> None:
        msg.aura_agent = self.original_aura_agent
        msg._configure_sse_runtime_for_tests(
            self.original_max_concurrency,
            self.original_queue_size,
        )

    def build_client(self) -> AsyncClient:
        app = FastAPI()
        app.include_router(msg.router)
        app.dependency_overrides[msg.get_current_user_id] = lambda: "authenticated-test-user"
        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def test_sse_capacity_is_fail_fast_instead_of_queueing(self) -> None:
        msg._configure_sse_runtime_for_tests(max_concurrency=2, queue_size=8)
        first_two_started = threading.Event()
        release_first_two = threading.Event()
        active_count = 0
        active_lock = threading.Lock()

        def fake_aura_agent(*_args, **_kwargs):
            nonlocal active_count
            with active_lock:
                active_count += 1
                if active_count == 2:
                    first_two_started.set()

            release_first_two.wait(timeout=2)
            yield {"event": "content", "content": "ok"}

        msg.aura_agent = fake_aura_agent

        async with self.build_client() as client:
            first = asyncio.create_task(self.post_sse(client, "user-1"))
            second = asyncio.create_task(self.post_sse(client, "user-2"))
            self.assertTrue(await asyncio.to_thread(first_two_started.wait, 1))

            started_at = time.perf_counter()
            overflow_response = await self.post_sse(client, "user-3")
            overflow_elapsed = time.perf_counter() - started_at

            self.assertEqual(overflow_response.status_code, 429)
            self.assertLess(overflow_elapsed, 0.15)

            release_first_two.set()
            first_response, second_response = await asyncio.gather(first, second)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

    async def test_sse_requests_within_capacity_complete_concurrently(self) -> None:
        request_count = 12
        sleep_seconds = 0.2
        msg._configure_sse_runtime_for_tests(
            max_concurrency=request_count,
            queue_size=request_count,
        )

        def fake_aura_agent(*_args, **_kwargs):
            time.sleep(sleep_seconds)
            yield {"event": "content", "content": "ok"}

        msg.aura_agent = fake_aura_agent

        async with self.build_client() as client:
            started_at = time.perf_counter()
            responses = await asyncio.gather(
                *(self.post_sse(client, f"user-{index}") for index in range(request_count))
            )
            elapsed = time.perf_counter() - started_at

        self.assertTrue(all(response.status_code == 200 for response in responses))
        # 仍远低于 12 个请求串行所需的 2.4 秒，同时为 Windows ASGI、认证依赖
        # 和线程池调度保留固定开销，避免把机器抖动误判为并发回归。
        self.assertLess(elapsed, sleep_seconds * 3.5)

    async def test_sse_uses_authenticated_user_instead_of_body_user_id(self) -> None:
        """聊天、游戏和宠物入口必须以 JWT 身份为准，忽略伪造的请求体用户。"""

        captured_user_ids: list[str] = []

        def fake_aura_agent(_message, user_id, *_args, **_kwargs):
            captured_user_ids.append(user_id)
            yield {"event": "content", "content": "ok"}

        msg.aura_agent = fake_aura_agent
        async with self.build_client() as client:
            response = await client.post(
                "/api/send/sse/",
                json={"message": "hello", "user_id": "spoofed-user"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_user_ids, ["authenticated-test-user"])

    async def post_sse(self, client: AsyncClient, user_id: str):
        return await client.post(
            "/api/send/sse/",
            json={
                "message": "hello",
                "user_id": "authenticated-test-user",
            },
        )


if __name__ == "__main__":
    unittest.main()
