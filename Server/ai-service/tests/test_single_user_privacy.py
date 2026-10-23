from __future__ import annotations

import base64
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import attachment_store, privacy
from app.core.auth_store import create_access_token, get_current_user_id, register_user
from app.routers import attachments, history, memory
from app.schemas.attachment import AttachmentUploadItem, AttachmentUploadRequest
from app.schemas.user import UserRegisterRequest


class RouteOwnershipTest(unittest.IsolatedAsyncioTestCase):
    """验证旧 ``userId`` 字段不能越过 JWT 权威身份。"""

    async def test_history_route_ignores_forged_path_user(self) -> None:
        current_user_id = str(uuid4())
        with patch("app.routers.history.get_history", return_value=[]) as get_history:
            response = await history.history(
                userId=str(uuid4()),
                current_user_id=current_user_id,
            )

        self.assertEqual(response.data, [])
        get_history.assert_called_once_with(current_user_id)

    async def test_memory_route_ignores_forged_query_user(self) -> None:
        current_user_id = str(uuid4())
        page = {"items": [], "total": 0, "page": 1, "pageSize": 10, "hasMore": False}
        with patch("app.routers.memory.list_memories_by_user", return_value=page) as list_memories:
            response = await memory.list_memory(
                current_user_id=current_user_id,
                userId=str(uuid4()),
            )

        self.assertEqual(response.data, page)
        self.assertEqual(list_memories.call_args.kwargs["user_id"], current_user_id)

    async def test_attachment_route_uses_jwt_owner(self) -> None:
        current_user_id = str(uuid4())
        request = AttachmentUploadRequest(userId=str(uuid4()), files=[])
        with patch("app.routers.attachments.save_attachments", return_value=[]) as save:
            response = await attachments.upload_attachments(request, current_user_id)

        self.assertEqual(response.data, {"items": []})
        save.assert_called_once_with(current_user_id, [])


class AttachmentStorageSecurityTest(unittest.TestCase):
    """验证附件签名、批量原子性和账号级物理删除。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_root = (Path(self.temp_dir.name) / "uploads").resolve()
        self.root_patch = patch.object(attachment_store, "UPLOAD_ROOT", self.upload_root)
        self.root_patch.start()
        self.user_id = str(uuid4())

    def tearDown(self) -> None:
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_batch_validation_happens_before_any_file_is_written(self) -> None:
        valid_png = b"\x89PNG\r\n\x1a\n" + b"test-payload"
        files = [
            self.upload_item("valid.png", "image/png", valid_png),
            self.upload_item("fake.png", "image/png", b"this is not a png"),
        ]

        with self.assertRaises(attachment_store.AttachmentValidationError):
            attachment_store.save_attachments(self.user_id, files)

        self.assertFalse(attachment_store.user_upload_dir(self.user_id).exists())

    def test_declared_mime_must_match_file_signature(self) -> None:
        jpeg_bytes = b"\xff\xd8\xff" + b"jpeg-payload"
        fake_png = self.upload_item("wrong.png", "image/png", jpeg_bytes)

        with self.assertRaisesRegex(attachment_store.AttachmentValidationError, "文件类型不一致"):
            attachment_store.save_attachment(self.user_id, fake_png)

    def test_delete_user_attachments_removes_all_physical_files(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"test-payload"
        attachment_store.save_attachment(
            self.user_id,
            self.upload_item("one.png", "image/png", png),
        )
        user_dir = attachment_store.user_upload_dir(self.user_id)
        self.assertEqual(len(list(user_dir.iterdir())), 2)

        deleted_count = attachment_store.delete_user_attachments(self.user_id)

        self.assertEqual(deleted_count, 2)
        self.assertFalse(user_dir.exists())

    @staticmethod
    def upload_item(name: str, content_type: str, raw: bytes) -> AttachmentUploadItem:
        """构造使用真实字节长度和 Base64 的附件请求项。"""

        return AttachmentUploadItem(
            fileName=name,
            contentType=content_type,
            size=len(raw),
            dataBase64=base64.b64encode(raw).decode("ascii"),
        )


class SingleUserAuthTest(unittest.IsolatedAsyncioTestCase):
    """验证唯一账号注册与删除后令牌失效。"""

    async def test_registration_rejects_second_account(self) -> None:
        count_result = SimpleNamespace(scalar_one=lambda: 1)
        session = SimpleNamespace(
            execute=AsyncMock(side_effect=[SimpleNamespace(), count_result]),
            rollback=AsyncMock(),
        )
        request = UserRegisterRequest(
            username="another-user",
            password="strong-password",
            sex=0,
        )

        with self.assertRaises(HTTPException) as raised:
            await register_user(session, request)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("唯一用户", raised.exception.detail)
        session.rollback.assert_awaited()

    async def test_token_subject_must_still_exist_in_database(self) -> None:
        user_id = str(uuid4())
        token = create_access_token(user_id)
        missing_result = SimpleNamespace(scalar_one_or_none=lambda: None)
        session = SimpleNamespace(execute=AsyncMock(return_value=missing_result))

        with self.assertRaises(HTTPException) as raised:
            await get_current_user_id(token, session)

        self.assertEqual(raised.exception.status_code, 401)


class PrivacyPurgeTest(unittest.IsolatedAsyncioTestCase):
    """验证跨存储清理会删除向量、checkpoint、用户和缓存引用。"""

    async def test_purge_user_data_covers_non_fk_stores(self) -> None:
        user_id = str(uuid4())
        proactive_id = uuid4()
        proactive_result = SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [proactive_id])
        )
        session = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    proactive_result,
                    SimpleNamespace(rowcount=2),
                    SimpleNamespace(rowcount=3),
                    SimpleNamespace(rowcount=4),
                    SimpleNamespace(rowcount=5),
                    SimpleNamespace(rowcount=1),
                ]
            ),
            commit=AsyncMock(),
            rollback=AsyncMock(),
        )

        with (
            patch("app.core.privacy.delete_user_attachments", return_value=6),
            patch("app.core.privacy.purge_user_redis_state") as purge_redis,
        ):
            counts = await privacy.purge_user_data(session, user_id)

        self.assertEqual(counts["attachments"], 6)
        self.assertEqual(counts["vector_memories"], 2)
        self.assertEqual(counts["checkpoint_writes"], 3)
        self.assertEqual(counts["checkpoint_blobs"], 4)
        self.assertEqual(counts["checkpoints"], 5)
        self.assertEqual(counts["users"], 1)
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        purge_redis.assert_called_once_with(user_id, [str(proactive_id)])


if __name__ == "__main__":
    unittest.main()
