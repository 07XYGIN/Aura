from fastapi import APIRouter, HTTPException

from app.core.attachment_store import AttachmentValidationError, save_attachments
from app.schemas.attachment import AttachmentUploadRequest
from app.schemas.response import SuccessResponse

router = APIRouter(
    prefix="/api/attachments",
    tags=["attachments"],
)


@router.post("", response_model=SuccessResponse, summary="Upload chat attachments")
async def upload_attachments(request: AttachmentUploadRequest):
    try:
        items = save_attachments(request.user_id, request.files)
    except AttachmentValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return SuccessResponse(data={"items": items})
