from __future__ import annotations

import base64
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

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


@dataclass(frozen=True)
class PreparedAttachment:
    """已经完成全部内存校验、尚未写入磁盘的附件。"""

    raw: bytes
    record: dict[str, Any]
    extension: str


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
    normalized_user_id = normalize_user_id(user_id)

    # 先把整批文件解码并验证完成，避免第二张文件不合法时第一张已经留在磁盘。
    prepared = [prepare_attachment(normalized_user_id, file) for file in files]
    if not prepared:
        return []

    user_dir = user_upload_dir(normalized_user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    created_paths: list[Path] = []
    try:
        for item in prepared:
            file_path, meta_path = persist_prepared_attachment(user_dir, item)
            created_paths.extend((file_path, meta_path))
    except OSError:
        for path in created_paths:
            path.unlink(missing_ok=True)
        remove_empty_directory(user_dir)
        raise

    return [public_attachment(item.record) for item in prepared]


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
    return save_attachments(user_id, [file])[0]


def prepare_attachment(user_id: str, file: AttachmentUploadItem) -> PreparedAttachment:
    """在不写磁盘的前提下完成 MIME、大小、签名和文件名校验。

    Returns:
        包含原始字节、公开/私有元数据和扩展名的不可变准备对象。

    Raises:
        AttachmentValidationError: 声明类型与真实文件头不一致或其他输入无效。
    """

    content_type = file.content_type.lower().strip()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise AttachmentValidationError("仅支持 jpg、png、webp、gif 图片")

    raw = decode_base64_payload(file.data_base64)
    if len(raw) > MAX_ATTACHMENT_BYTES:
        raise AttachmentValidationError("单张图片不能超过 10MB")
    if file.size and abs(file.size - len(raw)) > 1024:
        raise AttachmentValidationError("图片大小校验失败，请重新上传")
    if not matches_image_signature(raw, content_type):
        raise AttachmentValidationError("图片内容与声明的文件类型不一致")

    attachment_id = str(uuid4())
    safe_name = sanitize_file_name(file.file_name)
    extension = ALLOWED_IMAGE_TYPES[content_type]
    stored_name = f"{attachment_id}{extension}"
    file_path = user_upload_dir(user_id) / stored_name

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
    return PreparedAttachment(raw=raw, record=record, extension=extension)


def persist_prepared_attachment(
    user_dir: Path,
    prepared: PreparedAttachment,
) -> tuple[Path, Path]:
    """使用同目录临时文件和原子替换写入图片及 JSON 元数据。

    单个附件无法跨两个文件获得真正的文件系统事务，因此本函数在任一步失败时
    删除临时文件和已经落位的最终文件；外层再负责回滚本批更早的附件。
    """

    attachment_id = str(prepared.record["id"])
    file_path = user_dir / f"{attachment_id}{prepared.extension}"
    meta_path = user_dir / f"{attachment_id}.json"
    nonce = uuid4().hex
    file_temp = user_dir / f".{attachment_id}.{nonce}.image.tmp"
    meta_temp = user_dir / f".{attachment_id}.{nonce}.meta.tmp"
    try:
        file_temp.write_bytes(prepared.raw)
        meta_temp.write_text(
            json.dumps(prepared.record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(file_temp, file_path)
        os.replace(meta_temp, meta_path)
    except OSError:
        file_temp.unlink(missing_ok=True)
        meta_temp.unlink(missing_ok=True)
        file_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        raise
    return file_path, meta_path


def load_attachments(user_id: str, attachment_ids: list[str] | None) -> list[dict[str, Any]]:
    """从用户目录加载指定附件的公开元数据。

    无效 ID、缺失文件、损坏 JSON 和不属于当前用户的记录都会被忽略。
    """
    if not attachment_ids:
        return []

    records: list[dict[str, Any]] = []
    try:
        normalized_user_id = normalize_user_id(user_id)
    except AttachmentValidationError:
        return []
    user_dir = user_upload_dir(normalized_user_id)
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
        stored_path = Path(str(record.get("path") or "")).resolve()
        if (
            record.get("userId") == normalized_user_id
            and stored_path.parent == user_dir.resolve()
            and stored_path.is_file()
        ):
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


def matches_image_signature(raw: bytes, content_type: str) -> bool:
    """按受支持图片格式的魔数校验真实内容，不只信任客户端 MIME。"""

    if content_type == "image/jpeg":
        return raw.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return raw.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/gif":
        return raw.startswith((b"GIF87a", b"GIF89a"))
    if content_type == "image/webp":
        return len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
    return False


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
    """根据规范 UUID 返回位于上传根目录下一层的用户目录。"""

    return UPLOAD_ROOT / normalize_user_id(user_id)


def normalize_user_id(user_id: str) -> str:
    """把 JWT 用户 ID 规范为 UUID 字符串，拒绝可形成路径别名的输入。"""

    try:
        return str(UUID(str(user_id)))
    except (TypeError, ValueError) as exc:
        raise AttachmentValidationError("用户 ID 无效，无法保存附件") from exc


def delete_user_attachments(user_id: str) -> int:
    """删除用户完整附件目录并返回其中的文件数量。

    删除前会解析真实绝对路径并确认它仍是 ``UPLOAD_ROOT`` 的直接子目录；符号
    链接或任何越界路径都会拒绝处理，避免递归删除触及上传根目录以外的位置。
    """

    user_dir = user_upload_dir(user_id)
    if not user_dir.exists():
        return 0

    root = UPLOAD_ROOT.resolve()
    resolved_user_dir = user_dir.resolve()
    if resolved_user_dir.parent != root or resolved_user_dir == root:
        raise OSError("附件目录越过允许的上传根目录")

    file_count = sum(1 for path in resolved_user_dir.rglob("*") if path.is_file())
    shutil.rmtree(resolved_user_dir)
    return file_count


def remove_empty_directory(path: Path) -> None:
    """在批量写入回滚后删除空目录；目录非空或已不存在时保持不变。"""

    try:
        path.rmdir()
    except (FileNotFoundError, OSError):
        return


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
