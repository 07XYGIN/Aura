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
    """表示附件类型、大小或编码不符合上传约束。"""

    pass


def save_attachments(user_id: str, files: list[AttachmentUploadItem]) -> list[dict[str, Any]]:
    """校验单条消息的附件数量并逐个保存。

    Args:
        user_id: 附件所属用户 ID，用于隔离存储目录。
        files: 客户端上传的附件数据列表。

    Returns:
        可直接返回给客户端的附件元数据列表，不包含服务器文件路径。

    Raises:
        AttachmentValidationError: 附件过多，或任一附件未通过保存校验。
    """
    if len(files) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise AttachmentValidationError(f"每条消息最多上传 {MAX_ATTACHMENTS_PER_MESSAGE} 张图片")

    return [save_attachment(user_id, file) for file in files]


def save_attachment(user_id: str, file: AttachmentUploadItem) -> dict[str, Any]:
    """解码、校验并持久化一张图片及其元数据。

    Args:
        user_id: 附件所属用户 ID。
        file: 包含文件名、MIME 类型、大小和 Base64 数据的上传项。

    Returns:
        去除本地路径后的公开附件元数据。

    Raises:
        AttachmentValidationError: 文件类型、编码或大小不合法。

    Side Effects:
        在用户上传目录写入图片文件和同 ID 的 JSON 元数据文件。
    """
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
    """从用户目录加载指定附件的公开元数据。

    无效 ID、缺失文件、损坏 JSON 和不属于当前用户的记录都会被忽略。
    """
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
    """将附件元数据整理成可注入模型上下文的文字摘要。"""
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
    """筛选允许暴露给客户端或模型的附件字段，隐藏服务器路径。"""
    return {
        "id": record.get("id"),
        "fileName": record.get("fileName"),
        "contentType": record.get("contentType"),
        "size": record.get("size"),
        "summary": record.get("summary"),
        "createdAt": record.get("createdAt"),
    }


def decode_base64_payload(value: str) -> bytes:
    """解码纯 Base64 或 data URL；内容无效时抛出附件校验异常。"""
    payload = value.strip()
    if "," in payload and payload.startswith("data:"):
        payload = payload.split(",", 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise AttachmentValidationError("图片数据无法解析") from exc


def build_attachment_summary(file_name: str, content_type: str, size: int) -> str:
    """生成不包含虚构视觉信息的附件元数据摘要。"""
    return (
        f"用户上传了图片 {file_name}，类型 {content_type}，大小 {format_bytes(size)}。"
        "当前服务只记录附件元数据，尚未生成可靠视觉描述。"
    )


def sanitize_file_name(file_name: str) -> str:
    """去除路径和非法字符，并将展示文件名限制在 120 个字符内。"""
    name = Path(file_name or "image").name.strip()
    name = re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "_", name)
    return name[:120] or "image"


def user_upload_dir(user_id: str) -> Path:
    """根据安全化后的用户 ID 返回其独立上传目录。"""
    safe_user_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_id)[:80]
    return UPLOAD_ROOT / safe_user_id


def format_bytes(value: Any) -> str:
    """把字节数格式化为便于展示的 B、KB 或 MB 文本。"""
    if not isinstance(value, int):
        return "未知大小"
    if value < 1024:
        return f"{value}B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f}KB"
    return f"{value / 1024 / 1024:.1f}MB"


def is_uuid_like(value: str) -> bool:
    """粗略判断字符串是否可作为附件 UUID 文件名使用。"""
    return bool(re.fullmatch(r"[0-9a-fA-F-]{32,36}", value))
