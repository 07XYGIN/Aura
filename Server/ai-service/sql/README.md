# SQL 使用说明

根目录 `main.sql` 是当前 ORM 对应的一次性新库基线。日期 SQL 文件仍是已有数据库和按版本升级时的迁移链。

## Alembic 接管点

`20260918_0001` 是日期 SQL 链的 Alembic 接管点，`20260918_0002` 删除已退役的
专注、巴什博弈和宠物数据平面：

1. 新库先执行根目录 `main.sql`，再执行 `uv run alembic stamp head` 和 schema guard；
2. 尚未接管的已有库先执行完整日期迁移链，再执行 `uv run alembic stamp 20260918_0001`；
3. 已有库执行 `uv run alembic upgrade head` 删除退役数据表，最后运行 schema guard；
4. 后续结构变化只新增 Alembic revision，不再扩展日期 SQL 链。

不要在未核对结构的数据库上直接 stamp。日期 SQL 到此冻结，只保留为历史升级链。

## 新数据库

1. 在项目根目录执行 `main.sql`。
2. 启动应用；`PostgresSaver.setup()` 会创建和升级四张 `checkpoint_*` 表。
3. 回到 `Server/ai-service`，执行 `.\.venv\Scripts\python.exe tools\check_db_schema.py` 做完整结构核对。

`main.sql` 只面向空数据库，不会清理或改写已有表。

## 日期迁移链

1. 执行 `20260722_single_user_schema_cleanup.sql`，创建基础业务/记忆表并清理历史遗留结构。
2. 执行 `20260723_bash_game.sql`（历史步骤，接管后由 `20260918_0002` 删除）。
3. 执行 `20260723_companion_pet.sql`（历史步骤，接管后由 `20260918_0002` 删除）。
4. 执行 `20260723_relationship_continuity.sql`，创建关系线程当前状态和事件历史表。
5. 执行 `20260723_proactive_delivery.sql`，为主动消息增加幂等键、稳定投递 ID、领取租约和失败重试状态。
6. 执行 `20260723_relationship_items.sql`，创建双视角关系物件、私人语言、Aura 立场、纠偏规则和关系章节表。
7. 执行 `20260723_continuity_state.sql`，创建每日生活、情绪余温和共同想象场景表。
8. 执行 `20260723_offline_mind.sql`，创建离线思绪种子和每日睡前整理表。
9. 执行 `20260723_conditional_messages.sql`，创建时间胶囊、秘密保险箱和条件事件 inbox。
10. 执行 `20260724_focus_sessions.sql`（历史步骤，接管后由 `20260918_0002` 删除）。
11. 执行 `20260918_relationship_dynamics.sql`，创建玲凌持续自身状态与定性关系动态表。

## 已有数据库

先执行 `20260722_single_user_schema_cleanup.sql`，再执行尚未应用的日期增量，并按上面的接管步骤
升级到 Alembic head。`20260918_0002` 会永久删除三个退役功能的表和数据。
`20260723_proactive_delivery.sql` 会为历史主动消息回填稳定的 `delivery_message_id` 和零值尝试次数，
随后再设置默认值与非空约束；不会删除已有主动消息。
`20260723_relationship_items.sql` 会为已经执行过早期草稿的开发库补齐置信度、可变立场和章节幂等键，
保留已有关系数据，并重建与当前白名单一致的检查约束。

## 历史文件

其余日期更早的 SQL 仅用于追溯旧版本，不再作为新数据库的建库入口。其中部分文件会创建本次
迁移已经删除的聊天双轨、关系积分、情绪报告和商业化遗留表。
