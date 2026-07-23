"""单用户账号的完整隐私数据清理。

业务表可以通过 ``users`` 外键级联删除，但 LangGraph checkpoint、PGVector
metadata、文件系统附件和 Redis 临时状态都没有真实外键。本模块集中处理这些
跨存储数据，避免“账号已删除”只代表删掉一行用户资料。
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.attachment_store import delete_user_attachments
from app.core.redis_client import get_redis_client, safe_redis_call
from app.core.reply_timing_state import pending_bubbles_key
from app.core.silence_state import last_user_message_key, proactive_triggered_key
from app.db.models import LangchainPgEmbedding, ProactiveMessage, Users

PROACTIVE_QUEUE_KEY = "proactive_message_queue"
CHECKPOINT_TABLES_IN_DELETE_ORDER = (
    "checkpoint_writes",
    "checkpoint_blobs",
    "checkpoints",
)


class PrivacyPurgeError(RuntimeError):
    """表示账号隐私数据没有完成全部删除。"""


async def purge_user_data(session: AsyncSession, user_id: str) -> dict[str, int]:
    """物理删除一个用户分散在所有存储中的数据。

    Args:
        session: 当前请求的 PostgreSQL 异步会话。
        user_id: 已通过 JWT 和用户名核对的用户 UUID。

    Returns:
        各存储删除数量的字典，主要用于日志和测试，不向客户端暴露内部表名。

    Raises:
        PrivacyPurgeError: UUID 无效、附件清理失败或数据库事务失败。

    Notes:
        附件先物理删除，再执行数据库事务。这样数据库失败时用户仍可以重试；
        不会出现账号已经不存在、敏感文件却永久留在磁盘上的状态。Redis 是短期
        缓存，数据库提交后做尽力清理，失败的键也会按原 TTL 或失效 ID 自然退出。
    """

    try:
        parsed_user_id = UUID(str(user_id))
    except (TypeError, ValueError) as exc:
        raise PrivacyPurgeError("用户 ID 无效，无法执行隐私删除") from exc

    try:
        attachment_count = delete_user_attachments(str(parsed_user_id))
    except OSError as exc:
        raise PrivacyPurgeError("附件文件清理失败，账号尚未删除，请稍后重试") from exc

    counts: dict[str, int] = {"attachments": attachment_count}
    try:
        proactive_result = await session.execute(
            select(ProactiveMessage.id).where(ProactiveMessage.user_id == parsed_user_id)
        )
        proactive_ids = [str(value) for value in proactive_result.scalars().all()]

        vector_result = await session.execute(
            delete(LangchainPgEmbedding).where(
                LangchainPgEmbedding.cmetadata["user_id"].astext == str(parsed_user_id)
            )
        )
        counts["vector_memories"] = affected_rows(vector_result)

        for table_name in CHECKPOINT_TABLES_IN_DELETE_ORDER:
            # 表名来自上方固定白名单，用户值始终使用绑定参数，不能形成 SQL 注入。
            result = await session.execute(
                text(f"DELETE FROM {table_name} WHERE thread_id = :thread_id"),
                {"thread_id": str(parsed_user_id)},
            )
            counts[table_name] = affected_rows(result)

        user_result = await session.execute(
            delete(Users).where(Users.id == parsed_user_id)
        )
        if affected_rows(user_result) != 1:
            raise PrivacyPurgeError("用户不存在或已经删除")
        counts["users"] = 1
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    purge_user_redis_state(str(parsed_user_id), proactive_ids)
    logging.info(
        "用户隐私数据已完成物理删除 user_id=%s counts=%s",
        parsed_user_id,
        counts,
    )
    return counts


def purge_user_redis_state(user_id: str, proactive_message_ids: list[str]) -> None:
    """尽力删除用户的沉默、回复时序和主动消息队列缓存。

    Redis 不是真实数据源，所以连接失败不会把已经成功的 PostgreSQL 删除回滚。
    主动消息 ID 同时从全局有序队列移除，避免账号删除后调度器继续消费空引用。
    """

    redis_client = get_redis_client()
    keys = (
        last_user_message_key(user_id),
        proactive_triggered_key(user_id),
        pending_bubbles_key(user_id),
    )
    safe_redis_call("privacy_delete_user_keys", 0, redis_client.delete, *keys)
    if proactive_message_ids:
        safe_redis_call(
            "privacy_remove_proactive_queue_members",
            0,
            redis_client.zrem,
            PROACTIVE_QUEUE_KEY,
            *proactive_message_ids,
        )


def affected_rows(result: Any) -> int:
    """把 SQLAlchemy 结果的 ``rowcount`` 规范为非负整数。"""

    value = getattr(result, "rowcount", 0)
    return value if isinstance(value, int) and value > 0 else 0
