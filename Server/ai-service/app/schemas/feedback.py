"""对单条 Aura 回复的即时风格反馈。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReplyFeedbackRequest(BaseModel):
    """用户对一条已展示回复的行为纠偏。"""

    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(alias="messageId", min_length=1, max_length=128)
    category: Literal[
        "helpful",
        "too_long",
        "too_preachy",
        "too_clingy",
        "too_many_questions",
        "wrong_context",
    ]
