"""离线思绪管理接口使用的受限状态枚举。"""

from typing import Literal

ThoughtSeedStatus = Literal["pending", "queued", "used", "cancelled", "expired"]
