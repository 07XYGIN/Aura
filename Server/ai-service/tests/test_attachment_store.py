import base64
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import attachment_store
from app.schemas.attachment import AttachmentUploadItem


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLTeAAAAABJRU5ErkJggg=="
)


class AttachmentStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_root = (Path(self.temp_dir.name) / "uploads").resolve()
        self.root_patch = patch.object(attachment_store, "UPLOAD_ROOT", self.upload_root)
        self.root_patch.start()
        self.user_id = str(uuid4())

    def tearDown(self) -> None:
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_load_attachment_data_urls_returns_private_verified_image(self) -> None:
        saved = attachment_store.save_attachment(self.user_id, self.make_image("pixel.png"))

        data_urls = attachment_store.load_attachment_data_urls(self.user_id, [saved["id"]])
        public_records = attachment_store.load_attachments(self.user_id, [saved["id"]])

        self.assertEqual(data_urls, [f"data:image/png;base64,{base64.b64encode(TINY_PNG).decode('ascii')}"])
        self.assertEqual(public_records, [saved])
        self.assertNotIn("path", public_records[0])
        self.assertNotIn("dataBase64", public_records[0])
        self.assertNotIn("data:image", repr(public_records))

    def test_attachment_limit_remains_four_images_per_message(self) -> None:
        files = [self.make_image(f"pixel-{index}.png") for index in range(5)]

        with self.assertRaisesRegex(attachment_store.AttachmentValidationError, "最多上传 4 张图片"):
            attachment_store.save_attachments(self.user_id, files)

        self.assertEqual(attachment_store.MAX_ATTACHMENTS_PER_MESSAGE, 4)

    @staticmethod
    def make_image(name: str) -> AttachmentUploadItem:
        return AttachmentUploadItem(
            fileName=name,
            contentType="image/png",
            size=len(TINY_PNG),
            dataBase64=base64.b64encode(TINY_PNG).decode("ascii"),
        )
