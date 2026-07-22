# 当前 PostgreSQL 表结构

数据库已经收敛为单用户 Aura 当前实际使用的九张表。

## 业务模型表

| 表 | 功能 | 代码入口 |
| --- | --- | --- |
| `users` | 唯一用户的注册、登录和身份信息 | `app/core/auth_store.py` |
| `self_changelog_entry` | Aura 自我更新记录 | `app/core/agent/self_changelog.py`、`app/routers/admin.py` |
| `proactive_message` | 主动消息计划、状态和发送时间 | `app/core/proactive_scheduler.py` |
| `langchain_pg_collection` | 长期/中期向量记忆集合 | `app/core/memory/service.py` |
| `langchain_pg_embedding` | 向量记忆正文、向量和 metadata | `app/core/memory/service.py` |

## LangGraph 框架表

| 表 | 功能 |
| --- | --- |
| `checkpoints` | 对话线程状态快照 |
| `checkpoint_blobs` | checkpoint 二进制数据 |
| `checkpoint_writes` | 图执行过程中的待提交写入 |
| `checkpoint_migrations` | LangGraph checkpoint schema 版本 |

这些表由 `langgraph-checkpoint-postgres` 管理，不在本项目 ORM 中重复建模。

## 已删除的遗留数据平面

以下表没有进入当前主聊天、记忆或主动消息闭环，已由
`sql/20260722_single_user_schema_cleanup.sql` 删除：

- `admin_audit_log`
- `aura_profile`
- `chat_message`
- `conversation_feedback`
- `conversation_session`
- `daily_checkin`
- `emotion_insight_report`
- `emotion_snapshot`
- `invitation_code`
- `invitation_code_redemption`
- `memory_item`
- `memory_relation`
- `notification_plan`
- `prompt_version`
- `relationship_event`
- `relationship_state`
- `safety_event`
- `user_behavior_event`
- `user_export_job`
- `user_memory_entitlement`
- `user_profile`

聊天历史以 LangGraph checkpoint 为唯一事实源；记忆以 LangChain PGVector 表为唯一事实源。

## 自动核对

执行：

```powershell
.\.venv\Scripts\python tools\check_db_schema.py
```

脚本会检查：

- ORM 业务表和 PostgreSQL 业务表是否完全一致；
- 每张业务表的字段名、类型、可空性和默认值是否一致；
- 主键、唯一约束、检查约束、外键和普通索引是否一致；
- LangGraph 所需的四张框架表是否存在；
- 是否重新出现没有 ORM 模型的遗留业务表。
