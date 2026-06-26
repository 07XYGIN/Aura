from pydantic import BaseModel, ConfigDict, Field


class AttachmentUploadItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    content_type: str = Field(alias="contentType")
    size: int
    data_base64: str = Field(alias="dataBase64")


class AttachmentUploadRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    files: list[AttachmentUploadItem]
