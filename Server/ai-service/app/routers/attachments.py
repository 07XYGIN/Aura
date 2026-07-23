import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth_store import get_current_user_id
from app.core.attachment_store import AttachmentValidationError, save_attachments
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
