# 💖 Aura AI Service

<div align="center">

*Aura AI Service 是 Aura 的 Python AI 对话服务，负责编排、流式响应、工具调用、长期记忆和主动陪伴能力。*
*它把本地模型、LangGraph、PostgreSQL 检查点与 pgvector 记忆系统连接成一条可持续对话链路。*

---

### AI
![FastAPI](https://img.shields.io/badge/FastAPI-0.127+-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.x-1C3C3C?logo=langchain&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1.x-1C3C3C?logo=langchain&logoColor=white)
![DeepSeek](https://img.shields.io/badge/DeepSeek-Chat-4D6BFE)
![Ollama](https://img.shields.io/badge/Ollama-Embeddings-000000?logo=ollama&logoColor=white)

### 数据库
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1?logo=postgresql&logoColor=white)
![pgvector](https://img.shields.io/badge/pgvector-Embedding-4169E1)
![Redis](https://img.shields.io/badge/Redis-Cache-FF4438?logo=redis&logoColor=white)

</div>

---

## 📖 简介

**Aura AI Service** 位于 `Server/ai-service/`，是 Aura 的 FastAPI 异步 AI 服务。它通过 LangGraph 构建对话状态机，默认使用 DeepSeek 处理对话和判断任务，使用本地 Ollama Embedding 生成记忆向量，并通过 Server-Sent Events（SSE）向客户端输出回复事件。

服务同时提供聊天历史读取、长期记忆写入与语义检索、附件、位置、自我更新管理和主动消息调度能力。Web、PC 与根目录 `app/` Flutter 移动端后续都通过 `AI-Web/apps/bff` 消费这些能力。

---

## ✨ 功能介绍

### 🤖 AI 对话
- 基于 LangGraph `StateGraph` 编排聊天节点与工具节点
- 默认使用 DeepSeek 作为主对话模型，模型配置集中在 `app/core/llms.py`
- `/api/send/sse/` 通过 SSE 持续输出模型响应片段
- SSE 协议保持 `data: JSON` + `data: [DONE]` 兼容
- 每轮可输出 `emotion`、`memory_candidate` 和多段 `assistant_message` 事件

### 🧰 工具调用
- `get_weather`：查询天气，高德接口不可用时不会编造结果
- `save_memory_tool`：保存用户明确要求记住、或以后确实需要继续使用的信息
- `search_memory_tool`：按用户隔离检索历史记忆

时间属于每轮自动注入的上下文；情绪和互动状态属于内部判断；主动消息与记忆整理分别由后台调度器和维护模块执行，不绑定到普通聊天模型。

### 🧠 记忆与历史
- 使用 PostgreSQL Checkpointer 持久化 LangGraph 对话状态
- 使用 `PGVector` + PostgreSQL/pgvector 存储语义向量
- 使用 `nomic-embed-text:latest` 生成记忆 Embedding
- 记忆 metadata 包含 `user_id`、`title`、`create_time` 等字段
- 支持按用户清空历史、删除单条历史、分页列出记忆、语义检索记忆和删除记忆

### 🔌 API 端点
| 方法 | 端点 | 功能 |
| --- | --- | --- |
| POST | `/api/send/sse/` | 发送消息并返回 SSE 流式响应 |
| GET | `/api/history/{userId}` | 获取指定用户聊天历史 |
| DELETE | `/api/history/{userId}` | 清空指定用户聊天历史 |
| DELETE | `/api/history/{userId}/messages/{messageId}` | 删除单条聊天历史 |
| GET | `/api/memory/list` | 分页获取指定用户记忆 |
| GET | `/api/memory/getMemory` | 检索指定用户记忆 |
| GET | `/api/memory/retention` | 获取个人永久记忆与中期记忆策略 |
| DELETE | `/api/memory/list` | 清空指定用户记忆 |
| DELETE | `/api/memory/{memoryId}` | 删除指定记忆 |
| GET / POST / PATCH / DELETE | `/api/admin/*` | 记忆合并和自我更新接口 |

---

## 🏗️ 技术架构

```text
┌────────────────────────────────────────────────────────┐
│              Web / PC / Admin / Mobile                 │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼─────────────────────────────┐
│                    NestJS BFF 层                         │
│              userId 注入 · SSE 代理 · API 聚合            │
└──────────────────────────┬─────────────────────────────┘
                           │ /api/send/sse/  /api/memory/*
┌──────────────────────────▼─────────────────────────────┐
│                    FastAPI AI Service                   │
│       Router · Middleware · Exception Handler · Scheduler│
└───────────────┬───────────────────────────┬────────────┘
                │                           │
┌───────────────▼──────────────┐ ┌──────────▼─────────────┐
│         LangGraph Agent       │ │     Aura / Memory Store │
│ prompt · judges · chat tools  │ │ retrieval · maintenance │
└───────────────┬──────────────┘ └──────────┬─────────────┘
                │                           │
┌───────────────▼──────────────┐ ┌──────────▼─────────────┐
│    DeepSeek + Ollama Embed     │ │ PostgreSQL + pgvector   │
│       chat · judge · vector    │ │ checkpoints · vectors   │
└──────────────────────────────┘ └────────────────────────┘
```

---

## 📁 仓库结构

```text
ai-service/
├── main.py                         # FastAPI 应用入口
├── pyproject.toml                  # uv / Python 依赖配置
├── uv.lock                         # 锁定依赖版本
├── tools/
│   ├── check_mojibake.py           # 中文乱码扫描脚本
│   └── check_db_schema.py          # ORM 与 PostgreSQL 结构一致性检查
├── docs/
│   └── database-schema.md          # 当前保留表与删除表说明
├── sql/
│   ├── README.md                   # 当前基线与历史 SQL 使用说明
│   ├── ...                         # 仅用于追溯的历史增量迁移
│   └── 20260722_single_user_schema_cleanup.sql # 当前单用户结构清理迁移
└── app/
    ├── core/
    │   ├── agent/                  # LangGraph 主聊天编排
    │   │   ├── judges/             # 情绪、记忆、回合语境判断
    │   │   └── tools/              # 主聊天可调用的天气与记忆工具
    │   ├── memory/                 # 记忆存储、检索与后台维护
    │   ├── proactive/              # 主动消息计划与文案生成
    │   ├── attachment_store.py     # 附件存取
    │   ├── config.py               # 环境配置
    │   ├── emotion.py              # 情绪状态推导
    │   └── proactive_scheduler.py  # 主动消息调度
    ├── db/                         # SQLAlchemy 会话、模型和 schema guard
    ├── middleware/                 # 请求响应日志中间件
    ├── routers/                    # admin / msg / history / memory / attachments / location / user
    └── schemas/                    # Pydantic 请求和响应模型
```

---

## 🚀 快速开始

### 环境要求
- Python 3.12+
- uv
- PostgreSQL，并启用 pgvector
- Redis 7+
- DeepSeek API Key，用于主对话、情绪判断和记忆判断
- Ollama，并准备 `nomic-embed-text:latest` 用于本地记忆向量
- 高德地图 API Key，用于天气与位置工具

### 配置环境变量
在 `Server/ai-service/.env` 中配置本地环境变量：

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=Aura
DB_USER=postgres
DB_PASSWORD=your_password
JWT_SECRET_KEY=至少32字符的随机密钥
DEEPSEEK_API_KEY=your_deepseek_key
amap_key=your_amap_key
```

### 初始化数据库

新数据库和旧数据库都以 `sql/20260722_single_user_schema_cleanup.sql` 为当前基线。执行该文件后启动应用，
LangGraph 会自动创建或升级四张 `checkpoint_*` 表。早期 SQL 只用于追溯，不要作为新库的建库入口。

完整说明见 `sql/README.md`。

### 安装依赖
```bash
cd Server/ai-service
uv sync
```

### 启动 AI 服务
```bash
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

服务默认运行在：

```text
http://127.0.0.1:8000
```

### 调试 SSE 接口
```bash
curl -N -X POST http://127.0.0.1:8000/api/send/sse/ \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"你好，Aura\",\"userId\":\"demo-user\"}"
```

SSE 事件示例：

```text
data: {"event":"emotion","type":"emotion","emotion":{...}}

data: {"event":"memory_candidate","type":"memory_candidate","memory_candidate":{...}}

data: {"event":"assistant_message","type":"assistant_message","content":"我在呢","delayMs":500,...}

data: [DONE]
```

### 本地检查
```powershell
.\.venv\Scripts\python.exe tools\check_mojibake.py
.\.venv\Scripts\python.exe tools\check_db_schema.py
.\.venv\Scripts\python.exe -m compileall -q app main.py tools
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] FastAPI 应用、生命周期、中间件、CORS 与路由组织
- [x] LangGraph 对话状态机、工具节点和结构化 SSE 事件协议
- [x] PostgreSQL Checkpointer 对话状态持久化
- [x] PGVector 长期记忆保存、检索、分页、清空和删除
- [x] 天气、保存记忆、搜索记忆三个主聊天工具
- [x] 时间上下文自动注入、主动消息独立调度、记忆后台维护
- [x] 情绪语境与互动目标判断，不使用关键词关系积分
- [x] 附件、位置、记忆维护和自我更新接口
- [x] SSE 并发上限、队列背压和 `[DONE]` 兼容输出

### 🔜 规划中
- [ ] 补充核心 Agent、记忆和管理端接口测试
- [ ] 完善主动消息调度的可观测性与配置化开关
- [ ] 将更多 Aura 管理能力统一沉淀到 BFF 聚合层
