import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.auth_store import get_current_user_id
from app.core.attachment_store import AttachmentValidationError, open_attachment_file, save_attachments
from app.schemas.attachment import AttachmentUploadRequest
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/attachments", tags=["附件"])


@router.post("", response_model=SuccessResponse, summary="上传聊天附件")
async def upload_attachments(
    request: AttachmentUploadRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """保存聊天图片附件并返回可公开的元数据。

    Raises:
        HTTPException: 任一附件未通过类型、大小或 Base64 校验。
    """
    try:
        if request.user_id and request.user_id != current_user_id:
            logging.warning("附件请求体 userId 与 JWT 用户不一致，已使用 JWT 身份")
        items = save_attachments(current_user_id, request.files)
    except AttachmentValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return SuccessResponse(data={"items": items})


@router.get("/{attachment_id}/content", summary="读取当前用户的图片附件内容")
async def read_attachment_content(
    attachment_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """只在所有权和物理路径校验均通过后返回图片二进制内容。"""

    attachment = open_attachment_file(current_user_id, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="图片附件不存在")
    path, content_type = attachment
    return FileResponse(
        path,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )
