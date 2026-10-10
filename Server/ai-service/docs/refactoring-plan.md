# Aura 重构方案

## 目标

重构目标是让对话、记忆、关系状态和主动消息可以独立演进，并让每个外部依赖都有明确的失败边界。建议继续使用 FastAPI + LangGraph + PostgreSQL 的模块化单体，逐模块替换实现。重构期间保持 FastAPI 路由、SSE v1、LangGraph checkpoint 和现有数据库业务语义不变。

本次已经完成模型清理：聊天配置只保留 `qwen3.8-max`，仍为四种任务分别设置参数；本地 Ollama 接入及依赖已移除，线上 Embedding 尚未选型。已有记忆正文可以查看、删除和清空；新记忆写入、语义检索以及合并/晋升中的向量写入暂不可用，后台候选保存会跳过并记录日志。原有向量、正文和 checkpoint 均保留，数据库结构和表的归属未变。本次只交付清理及接口预留，以下阶段是后续建议。

## 现状问题

- `app/core/agent/agent_graph.py` 约 2,000 行，同时负责图定义、提示词上下文、历史读写、回复解析、关系副作用和记忆候选保存。
- `app/core/memory/service.py` 约 1,300 行，同时包含向量存储、SQL 查询、检索排序、生命周期维护和合并算法。
- `proactive_scheduler.py` 同时承担计划生成、数据库租约、消息文案、投递和失败重试。
- 同步 SQLAlchemy、原生 psycopg、LangChain PGVector 和 LangGraph checkpoint 混用，边界不清晰，测试需要大量全局 patch。
- 多端 Web、PC、Flutter 共享后端，但 API 合约没有集中生成和版本校验。
- Embedding 模型切换没有版本、维度和重建流程，不能直接把不同模型的向量写入同一个 collection。

## 目标结构

```text
app/
  routers/              # 保留路由、鉴权、请求和响应边界
  schemas/              # 保留 API DTO，供 OpenAPI 导出
  core/
    config.py           # 环境配置；逐步解开导入配置就创建客户端的依赖
    llms.py             # 一个 Qwen 配置，四种任务参数和统一重试策略
    agent/
      orchestrator.py   # 现有回合用例入口
      agent_graph.py    # 收敛成图组装和兼容导出
      nodes.py          # 对话和工具节点
      history.py        # checkpoint 历史、分支、重试
      effects.py        # 关系、记忆、审批副作用编排
      structured_reply.py
      protocol.py       # 现有 SSE v1 合约
      prompts/v1/       # 保留已有版本化提示词
    memory/
      service.py        # 用例入口和兼容函数
      embeddings.py     # 线上向量客户端边界
      repository.py    # PGVector 和正文读写
      retrieval.py     # 检索、过滤、排序
      lifecycle.py     # 保留、过期、晋升
      merge.py         # 合并候选和确认
    continuity/        # 保留关系模块，逐步分离纯规则与持久化
    proactive/
      planner.py       # 复用现有计划规则
      service.py       # 文案与投递用例
      outbox.py        # 租约、幂等、投递状态
    proactive_scheduler.py  # 收敛为定时唤醒与任务编排
  db/                   # 保留 ORM、会话、schema audit
```

依赖方向为 `router -> 用例 service/orchestrator -> 规则函数和 repository/client`。规则函数不创建数据库或网络连接；跨模块输入输出逐步收敛为现有 Pydantic 合约或小型 dataclass。只有真实需要替换、隔离或测试的外部依赖才增加接口。

## 分阶段执行

### 阶段 0：基线和观测

1. 锁定现有 SSE v1、模型调用、记忆 API、关系状态和主动消息的行为样例。
2. 增加 request/turn ID、模型耗时、token 用量、向量服务耗时、失败类型和重试次数指标；日志禁止记录聊天正文和 API Key。
3. 复用现有单测和关系回归数据，补齐拆分影响到的端到端行为；隔离测试中的 Redis 和外部模型访问。当前基线为 337 项后端 unittest，3 项环境条件跳过。

验收：全量后端测试通过；SSE 事件序列、数据库 schema guard 和关系回归评测结果与重构前一致。

### 阶段 1：模型和基础设施边界

1. 保留一个 Qwen 聊天配置和四种任务参数，复用 `create_llm`、`reliability.py`，统一超时、重试预算和错误分类。将客户端创建从模块导入移到服务初始化或可注入工厂。
2. 供应商确定后在 `core/memory/embeddings.py` 实现线上适配，满足 LangChain `Embeddings` 接口；额外记录 `provider/model/dimension/version` 和批量限制。
3. 优先复用 collection 的现有 metadata 保存版本标识；相同维度但来自不同模型的向量也不能混写。提供商、模型或维度变化都触发重建。
4. 建立离线重建命令：分页读取正文，调用线上模型批量生成向量，写入新 collection。保留 `memory_key`、用户、来源和生命周期字段，按原始 ID 幂等写入，支持断点续跑。
5. 当前保存、列表、删除、合并和清理都使用固定 collection 名。统一解析长期/中期集合后，冻结向量写入、校验数量/维度/检索样例并一次切换所有读写入口；逐用户确认不会丢失或重复展示旧记忆。不同模型的相似度分布不同，重测现有检索和去重阈值。

验收：Embedding 服务不可用时聊天仍能回复；记忆功能返回可解释状态；重建命令可断点续跑、可重复执行且不修改原 collection。该阶段依赖供应商选择，选型期间可以先推进阶段 2 和 3。

### 阶段 2：拆分记忆模块

按以下顺序搬迁，保持原函数做兼容 facade，避免一次性改动所有调用方：

1. `memory/repository.py`：向量读写、正文列表、按用户过滤、删除。
2. `memory/retrieval.py`：相似检索、阈值、冷却、排序、格式化上下文。
3. `memory/lifecycle.py`：长期/中期状态、过期、晋升、supersede。
4. `memory/merge.py`：候选簇、主题合并、人工确认。
5. 原 `memory/service.py`：最终仅保留用例编排、权限、不可用状态和事务边界。

验收：API 路由只调用用例 service；repository 可以用 fake adapter 测试；向量 provider 可以替换而无需修改业务规则。为重复保存、合并、审批重放建立稳定来源键；模型识别出的候选、用户批准和实际保存成功必须区分。

### 阶段 3：拆分对话图

先提取 `history.py` 和 `effects.py`，再提取 `nodes.py`。复用现有 `prompt_builder.py`、`structured_reply.py`、`protocol.py` 和 `orchestrator.py`，将 `agent_graph.py` 收敛为组装入口。每个节点只读写 typed state；关系事件、记忆候选、附件和主动消息通过用例函数执行。同步节点和同步数据库操作继续在线程池中运行，逐条审查异步路由，避免阻塞事件循环。

验收：主对话、工具调用、结构化回复、分支、重试和审批回归测试通过；图可以在没有数据库副作用的情况下执行纯 prompt/eval。

### 阶段 4：拆分主动消息和后台任务

先在同一个进程内拆出 `proactive/outbox.py`，复用现有 planner/service。scheduler 只负责定时唤醒和编排；计划规则、资格判断、文案生成和条件消息触发各有明确入口。只有需要多进程部署时再提供独立 worker 命令。Redis 只做唤醒和加速，PostgreSQL 继续作为事实源。

验收：进程重启、重复领取、租约过期、失败重试和幂等投递测试通过；不会重复写聊天历史或重复发送同一 `delivery_message_id`。

### 阶段 5：统一 API 和前端客户端

1. 以 OpenAPI 为 HTTP 真相源，生成 TypeScript 和 Dart 类型。
2. 统一分页、错误、鉴权、SSE envelope 和 503 能力状态。SSE schema 单独从 Pydantic 导出，OpenAPI 本身不能自动描述所有流式事件。
3. Web、PC、Admin 在现有 workspace package 中共享 TypeScript API client 和 SSE 解析器；Flutter 使用由同一协议生成的 Dart 类型及独立解析器，复用事件样例验收。统一 token 过期行为，页面只处理 view state。
4. 删除旧参数兼容层前，先记录客户端版本和使用情况，至少保留一个迁移周期。

验收：多端使用同一协议源；SSE 断线、重复事件、过期 token 和向量服务 503 都有一致行为。明确当前重连能力，未实现事件持久化前不承诺任意位置续传。Web 与 PC 哪个作为长期主客户端另行决定，先盘点功能差异。

## 数据和发布策略

- 每次数据库结构变化同时更新 ORM、根目录 `main.sql`、Alembic revision；表归属或生命周期变化同步 database-schema 文档。按仓库约定升级 `.env` 对应本地库，运行 schema check，核对后才能对新导入的库 stamp。
- Embedding 重建使用新 collection 或新版本前缀，不直接覆盖旧向量；切换后保留旧 collection 一个观察周期，再单独提交删除迁移。
- 每次提交只拆一个职责，保留短期兼容导出。纯代码拆分用测试和提交回退；仅涉及向量切换或新写入行为时使用临时开关，避免长期维护两套实现。
- 向量发布顺序：停写 -> 新集合批量重建 -> 验证 -> 统一切换读写 -> 恢复写入。模型确定后再执行，当前不发送旧记忆正文。
- 切换后产生的新记忆也必须纳入回退方案；只切回旧集合会丢失它们的可见性。回退时停写并处理差异正文后再切换。数据库迁移保持向前兼容。

## 必须先定的决策

1. 线上 Embedding 供应商、模型名、维度、限流和数据驻留区域。
2. 是否允许将已有记忆正文发送到第三方 Embedding 服务，以及脱敏规则。
3. 线上 Embedding 失败时，新记忆如何处理。建议后续先持久化正文和待索引状态，再由任务重试；这需要额外设计和数据库迁移，本次没有实现。
4. Web、PC、Flutter 的最低客户端版本和旧 API 兼容期限。

## 完成标准

- 生产只配置一个聊天模型；Embedding provider 可替换且有版本标识。
- 任何外部模型或向量服务失败都不会伪造“已记住”或历史事实。
- 对话、记忆、关系和主动消息的用例服务可独立测试，并随同一后端版本发布。
- 后端 unittest、关系评测、schema check、前端构建和线上向量重建抽样验证全部通过。
