# SQL 使用说明

当前数据库基线是 `20260722_single_user_schema_cleanup.sql`，其后按日期执行功能增量迁移。

## 新数据库

1. 执行 `20260722_single_user_schema_cleanup.sql`，创建基础业务/记忆表。
2. 执行 `20260723_bash_game.sql`，创建巴什博弈会话和行动表。
3. 启动应用；`PostgresSaver.setup()` 会创建和升级四张 `checkpoint_*` 表。
4. 回到项目根目录，执行 `.\.venv\Scripts\python.exe tools\check_db_schema.py` 做完整结构核对。

## 已有数据库

先执行 `20260722_single_user_schema_cleanup.sql`，再执行尚未应用的日期增量。迁移会保留当前功能数据，
移除未使用的旧表和 `proactive_message.notification_plan_id`，并补齐当前索引与约束。脚本可以重复执行。

## 历史文件

其余日期更早的 SQL 仅用于追溯旧版本，不再作为新数据库的建库入口。其中部分文件会创建本次
迁移已经删除的聊天双轨、关系积分、情绪报告和商业化遗留表。
