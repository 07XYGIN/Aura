# SQL 使用说明

当前数据库基线是 `20260722_single_user_schema_cleanup.sql`，其后按日期执行功能增量迁移。

## 新数据库

1. 执行 `20260722_single_user_schema_cleanup.sql`，创建基础业务/记忆表。
2. 执行 `20260723_bash_game.sql`，创建巴什博弈会话和行动表。
3. 执行 `20260723_companion_pet.sql`，创建共同宠物和宠物事件表。
4. 执行 `20260723_relationship_continuity.sql`，创建关系线程当前状态和事件历史表。
5. 执行 `20260723_proactive_delivery.sql`，为主动消息增加幂等键、稳定投递 ID、领取租约和失败重试状态。
6. 执行 `20260723_relationship_items.sql`，创建双视角关系物件、私人语言、Aura 立场、纠偏规则和关系章节表。
7. 执行 `20260723_continuity_state.sql`，创建每日生活、情绪余温和共同想象场景表。
8. 执行 `20260723_offline_mind.sql`，创建离线思绪种子和每日睡前整理表。
9. 启动应用；`PostgresSaver.setup()` 会创建和升级四张 `checkpoint_*` 表。
10. 回到项目根目录，执行 `.\.venv\Scripts\python.exe tools\check_db_schema.py` 做完整结构核对。

## 已有数据库

先执行 `20260722_single_user_schema_cleanup.sql`，再执行尚未应用的日期增量。迁移会保留当前功能数据，
移除未使用的旧表和 `proactive_message.notification_plan_id`，并补齐当前索引与约束。脚本可以重复执行。
`20260723_proactive_delivery.sql` 会为历史主动消息回填稳定的 `delivery_message_id` 和零值尝试次数，
随后再设置默认值与非空约束；不会删除已有主动消息。
`20260723_relationship_items.sql` 会为已经执行过早期草稿的开发库补齐置信度、可变立场和章节幂等键，
保留已有关系数据，并重建与当前白名单一致的检查约束。

## 历史文件

其余日期更早的 SQL 仅用于追溯旧版本，不再作为新数据库的建库入口。其中部分文件会创建本次
迁移已经删除的聊天双轨、关系积分、情绪报告和商业化遗留表。
