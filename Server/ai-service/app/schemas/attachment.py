from pydantic import BaseModel, ConfigDict, Field


class AttachmentUploadItem(BaseModel):
    """单个聊天附件的文件元数据和 Base64 内容。"""

    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    content_type: str = Field(alias="contentType")
    size: int
    data_base64: str = Field(alias="dataBase64")


class AttachmentUploadRequest(BaseModel):
    """一次附件上传请求，包含所属用户和附件列表。"""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    files: list[AttachmentUploadItem]
