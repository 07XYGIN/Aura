from pydantic import BaseModel, ConfigDict, Field


class AttachmentUploadItem(BaseModel):
    """单个聊天附件的文件元数据和 Base64 内容。"""

    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    content_type: str = Field(alias="contentType")
    size: int
    data_base64: str = Field(alias="dataBase64")


class AttachmentUploadRequest(BaseModel):
    """一次附件上传请求。

    ``userId`` 仅为旧客户端兼容字段；服务端所有权始终来自 Bearer JWT。
    """

    model_config = ConfigDict(populate_by_name=True)

    user_id: str | None = Field(default=None, alias="userId")
    files: list[AttachmentUploadItem]
