"""关系物件和关系章节管理接口使用的受限枚举。"""

from typing import Literal

RelationshipItemType = Literal[
    "shared_memory",
    "nickname",
    "running_joke",
    "codeword",
    "ritual",
    "shared_object",
    "action_style",
    "aura_stance",
    "interaction_rule",
    "boundary",
]
RelationshipItemStatus = Literal["active", "inactive", "superseded"]
RelationshipWorldLayer = Literal["reality", "shared_history", "imagined", "wish", "promise"]
