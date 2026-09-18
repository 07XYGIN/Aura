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
                       ├── AuraInternalState + RelationshipDynamics
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
pnpm --filter @ai-web/pc build
pnpm --filter @ai-web/web build
```

数据库以 `main.sql` 为新库引导、日期 SQL 为 Alembic 接管前的存量升级链，并由
ORM/schema guard 校验。结构通过校验后 stamp `20260918_0001`；后续变化只允许新增
Alembic revision，不再扩展日期 SQL 链。
