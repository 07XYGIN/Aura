# 当前 PostgreSQL 表结构

数据库已经收敛为单用户 Aura 当前实际使用的十一张业务表。

## 业务模型表

| 表 | 功能 | 代码入口 |
| --- | --- | --- |
| `users` | 唯一用户的注册、登录和身份信息 | `app/core/auth_store.py` |
| `self_changelog_entry` | Aura 自我更新记录 | `app/core/agent/self_changelog.py`、`app/routers/admin.py` |
| `proactive_message` | 主动消息可靠 outbox：计划、领取租约、幂等投递、重试与终态 | `app/core/proactive_scheduler.py` |
| `relationship_thread` | 未完成事项、后续关心、冲突、承诺和项目任务的当前状态 | `app/core/continuity/` |
| `relationship_thread_event` | 关系线程每次创建、更新、跟进、解决或放弃的不可变事件 | `app/core/continuity/` |
| `bash_game_session` | 巴什博弈的当前局面、参与者轮次和并发版本 | `app/core/games/bash/service.py` |
| `bash_game_move` | 巴什博弈每一步不可变行动历史 | `app/core/games/bash/service.py` |
| `companion_pet` | 小乔与 Aura 共同宠物的当前状态 | `app/core/pet/service.py` |
| `pet_event` | 宠物领养、照顾、改名和成长事件 | `app/core/pet/service.py` |
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

聊天历史以 LangGraph checkpoint 为唯一事实源；语义记忆以 LangChain PGVector 表为事实源；
需要明确生命周期和幂等更新的跨对话事项以 `relationship_thread` 及其事件表为事实源。

## 主动消息可靠投递

`proactive_message` 是主动消息投递的 PostgreSQL 权威来源。Redis 可以用于唤醒或加速，
但不能代替数据库中的计划和最终状态。

| 字段或约束 | 语义 |
| --- | --- |
| `dedupe_key varchar(160)` | 可空业务幂等键；`(user_id, dedupe_key)` 唯一，避免重复计划同一件事 |
| `delivery_message_id varchar(128)` | 非空稳定消息 ID；创建、进程重启和重试时保持不变 |
| `attempt_count integer` | 非空且默认 `0`，记录已经执行的投递尝试次数 |
| `claimed_until timestamptz` | worker 租约截止时间；过期的 `processing` 消息可以被其他 worker 接管 |
| `last_error text` | 最近一次失败原因，供重试策略和运维诊断使用 |
| `cancelled_at timestamptz` | 进入 `cancelled` 终态的时间 |
| `chk_proactive_message_status` | 只允许 `pending`、`processing`、`sent`、`skipped`、`failed`、`cancelled` |
| `idx_proactive_message_claim` | 按 `(status, scheduled_at, claimed_until)` 查找应领取或租约已过期的消息 |

`sent`、`skipped`、`failed` 和 `cancelled` 是终态。投递失败但仍可重试时，业务层应增加
`attempt_count`、记录 `last_error` 并重新置为 `pending`；达到上限后才进入 `failed`。

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
