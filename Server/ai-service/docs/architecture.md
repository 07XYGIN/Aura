# Aura 模块化单体架构

FastAPI 是 Aura 唯一后端入口。HTTP 路由只负责鉴权、请求模型和响应；一轮对话由
`TurnOrchestrator` 编排，领域状态和副作用分别落在独立模块中。

```text
Web / PC / Admin / Mobile
            │ HTTP + SSE v1
            ▼
FastAPI router → TurnOrchestrator → LangGraph conversation
                       │
                       ├── ActivityRegistry → external activity handlers
                       ├── PromptBuilder → prompts/v1/*.md
                       ├── RelationshipEvent → state transition
                       ├── AffectState → decay / reinforce / resolve
                       ├── RelationshipDynamics → stage / phase / tone
                       ├── Impulse candidates → resolver → 0..1 impulse
                       └── typed SSE envelope → clients

ProactiveScheduler → ProactivePlanner → ProactiveMessage outbox → history
```

## 依赖方向

- `routers/` 不判断活动规则、不拼 prompt、不直接做关系决策。
- `core/agent/orchestrator.py` 只编排一轮；LangGraph 节点继续负责模型和工具流程。
- `core/activities/` 通过统一 handler contract 注册活动，新活动不修改聊天路由。
- `core/proactive/planner.py` 决定是否联系、原因和文案；scheduler 只加载状态、持久化和投递。
- `core/agent/prompts/v1/` 是当前 prompt 版本，`prompt.py` 仅保留兼容导出。
- `core/agent/models.py` 定义跨模块传递的枚举和 Pydantic 合约。

## SSE v1

每个 JSON 事件包含 `version`、`eventId`、`turnId`、`sequence`、`type`、
`timestamp` 和 `payload`。`type` 使用 `turn.started`、`message.created`、
`activity.updated`、`turn.completed` 等稳定名称。迁移期仍保留旧 `event` 和业务字段；
`data: [DONE]` 暂时继续作为兼容终止帧。

## 验证

```powershell
uv run python -m unittest discover -s tests -p 'test_*.py'
uv run python tools/run_relationship_evals.py
uv run python tools/run_relationship_conversations.py --live
pnpm --filter @ai-web/pc build
pnpm --filter @ai-web/web build
```

数据库以仓库根目录唯一的 `main.sql` 作为新库完整基线，已有数据库只使用 Alembic Python
revision 升级，并由 ORM/schema guard 校验。新库导入基线后 stamp 当前 head；后续结构变化必须
同时更新 ORM、`main.sql` 和 Alembic revision，不允许新增第二个 SQL 文件。

`run_relationship_evals.py` 只检查预写回复样例，不代表真实模型质量。`run_relationship_conversations.py --live`
使用当前模型、生产判断器/状态函数/提示词/输出解析器，连续运行合成对话，报告实际回复、状态和违规项。
评测状态只存内存，不调用工具、不读写用户记忆和 checkpoint；它不是 HTTP/SSE 全链路压测。
输出格式需要生产 formatter 修复时单独标记，供应商错误或修复失败都算失败。

关系事件使用保守的否定、引用、假设和目标过滤；未知语境不推进关系阶段。离线时长只形成
缺席事实，不自动把关系改为疏远。内部 affect 可以持续，但任务/拒绝优先，表达冷却只读取
assistant 实际正文。明确的 `too_clingy` 反馈抑制主动醋意和挽留；关系主动联系在上一条未获
回应时暂停，线程回访必须已到期且允许主动跟进。
