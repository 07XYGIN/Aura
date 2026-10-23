"""人工审批接口的请求模型。"""

from pydantic import BaseModel


class ApprovalResolutionRequest(BaseModel):
    """用户对一条冻结的持久化效果作出的明确决定。"""

    approved: bool
