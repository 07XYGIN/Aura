from __future__ import annotations

import base64
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.attachment import AttachmentUploadItem

UPLOAD_ROOT = Path(os.getenv("AURA_UPLOAD_DIR", "uploads")).resolve()
MAX_ATTACHMENTS_PER_MESSAGE = 4
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class AttachmentValidationError(ValueError):
    pass


def save_attachments(user_id: str, files: list[AttachmentUploadItem]) -> list[dict[str, Any]]:
    if len(files) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise AttachmentValidationError(f"每条消息最多上传 {MAX_ATTACHMENTS_PER_MESSAGE} 张图片")

    return [save_attachment(user_id, file) for file in files]


def save_attachment(user_id: str, file: AttachmentUploadItem) -> dict[str, Any]:
    content_type = file.content_type.lower().strip()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise AttachmentValidationError("仅支持 jpg、png、webp、gif 图片")

    raw = decode_base64_payload(file.data_base64)
    if len(raw) > MAX_ATTACHMENT_BYTES:
        raise AttachmentValidationError("单张图片不能超过 10MB")
    if file.size and abs(file.size - len(raw)) > 1024:
        raise AttachmentValidationError("图片大小校验失败，请重新上传")

    attachment_id = str(uuid4())
    safe_name = sanitize_file_name(file.file_name)
    extension = ALLOWED_IMAGE_TYPES[content_type]
    user_dir = user_upload_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{attachment_id}{extension}"
    file_path = user_dir / stored_name
    meta_path = user_dir / f"{attachment_id}.json"
    file_path.write_bytes(raw)

    record = {
        "id": attachment_id,
        "userId": user_id,
        "fileName": safe_name,
        "contentType": content_type,
        "size": len(raw),
        "path": str(file_path),
        "createdAt": datetime.now(UTC).isoformat(),
        "summary": build_attachment_summary(safe_name, content_type, len(raw)),
    }
    meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return public_attachment(record)


def load_attachments(user_id: str, attachment_ids: list[str] | None) -> list[dict[str, Any]]:
    if not attachment_ids:
        return []

    records: list[dict[str, Any]] = []
    user_dir = user_upload_dir(user_id)
    for attachment_id in attachment_ids[:MAX_ATTACHMENTS_PER_MESSAGE]:
        if not is_uuid_like(attachment_id):
            continue
        meta_path = user_dir / f"{attachment_id}.json"
        if not meta_path.exists():
            continue
        try:
            record = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if record.get("userId") == user_id:
            records.append(public_attachment(record))
    return records


def format_attachment_context(attachments: list[dict[str, Any]]) -> str:
    if not attachments:
        return "本轮没有附件。"

    lines = [
        "本轮附件摘要：",
    ]
    for item in attachments:
        lines.append(
            f"- {item.get('fileName')}（{item.get('contentType')}，{format_bytes(item.get('size'))}）："
            f"{item.get('summary')}"
        )
    lines.append("只基于附件摘要和用户文字回应；没有视觉描述时，不要编造图片画面。")
    return "\n".join(lines)


def public_attachment(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "fileName": record.get("fileName"),
        "contentType": record.get("contentType"),
        "size": record.get("size"),
        "summary": record.get("summary"),
        "createdAt": record.get("createdAt"),
    }


def decode_base64_payload(value: str) -> bytes:
    payload = value.strip()
    if "," in payload and payload.startswith("data:"):
        payload = payload.split(",", 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise AttachmentValidationError("图片数据无法解析") from exc


def build_attachment_summary(file_name: str, content_type: str, size: int) -> str:
    return (
        f"用户上传了图片 {file_name}，类型 {content_type}，大小 {format_bytes(size)}。"
        "当前服务只记录附件元数据，尚未生成可靠视觉描述。"
    )


def sanitize_file_name(file_name: str) -> str:
    name = Path(file_name or "image").name.strip()
    name = re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "_", name)
    return name[:120] or "image"


def user_upload_dir(user_id: str) -> Path:
    safe_user_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_id)[:80]
    return UPLOAD_ROOT / safe_user_id


def format_bytes(value: Any) -> str:
    if not isinstance(value, int):
        return "未知大小"
    if value < 1024:
        return f"{value}B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f}KB"
    return f"{value / 1024 / 1024:.1f}MB"


def is_uuid_like(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F-]{32,36}", value))
