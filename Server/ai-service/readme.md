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
![Ollama](https://img.shields.io/badge/Ollama-Qwen3-000000?logo=ollama&logoColor=white)

### 数据库
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1?logo=postgresql&logoColor=white)
![pgvector](https://img.shields.io/badge/pgvector-Embedding-4169E1)
![Redis](https://img.shields.io/badge/Redis-Cache-FF4438?logo=redis&logoColor=white)

</div>

---

## 📖 简介

**Aura AI Service** 位于 `Server/ai-service/`，是 Aura 的 FastAPI 异步 AI 服务。它通过 LangGraph 构建对话状态机，使用 Ollama 本地模型处理多轮对话，并通过 Server-Sent Events（SSE）向客户端持续输出响应片段。

服务同时提供聊天历史读取、长期记忆写入与语义检索、附件、位置、情绪、关系状态、管理端资源查询和主动消息调度能力。Web、PC 与根目录 `app/` Flutter 移动端后续都通过 `AI-Web/apps/bff` 消费这些能力。

---

## ✨ 功能介绍

### 🤖 AI 对话
- 基于 LangGraph `StateGraph` 编排聊天节点与工具节点
- 使用 `qwen3:8b` 作为主要对话模型
- `/api/send/sse/` 通过 SSE 持续输出模型响应片段
- SSE 协议保持 `data: JSON` + `data: [DONE]` 兼容
- 每轮可输出 `emotion`、`memory_candidate`、`relationship_delta` 和多段 `content` 事件

### 🧰 工具调用
- `get_weather`：查询天气，高德接口不可用时不会编造结果
- `save_memory_tool`：分析用户消息，将值得长期保存的信息写入记忆库
- `search_memory_tool`：按用户隔离检索历史记忆
- `get_current_datetime`：返回指定时区的当前日期、时间和星期
- `get_relationship_status`：基于当前消息估算关系状态和亲密度
- `get_emotional_support_advice`：根据用户情绪给出安抚策略和回复方向

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
| GET | `/api/memory/retention` | 获取免费记忆保留状态 |
| DELETE | `/api/memory/list` | 清空指定用户记忆 |
| DELETE | `/api/memory/{memoryId}` | 删除指定记忆 |
| POST | `/api/aura/*` | 写入会话、消息、记忆、关系和反馈等 Aura 数据 |
| GET / POST / PATCH / DELETE | `/api/admin/*` | 管理端资源、记忆合并和自我更新接口 |

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
│  prompt · tools · structured  │ │  history · metadata     │
└───────────────┬──────────────┘ └──────────┬─────────────┘
                │                           │
┌───────────────▼──────────────┐ ┌──────────▼─────────────┐
│      Ollama / Qwen Models     │ │ PostgreSQL + pgvector   │
│    chat · embedding · judge    │ │ checkpoints · vectors   │
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
│   └── check_mojibake.py           # 中文乱码扫描脚本
└── app/
    ├── core/
    │   ├── agent/                  # LangGraph、提示词、工具和结构化协议
    │   ├── aura_store.py           # Aura 业务数据存取
    │   ├── attachment_store.py     # 附件存取
    │   ├── config.py               # 环境配置
    │   ├── emotion.py              # 情绪状态推导
    │   └── proactive_scheduler.py  # 主动消息调度
    ├── db/                         # SQLAlchemy 会话、模型和 schema guard
    ├── middleware/                 # 请求响应日志中间件
    ├── routers/                    # user / msg / history / memory / aura / admin
    ├── schemas/                    # Pydantic 请求和响应模型
    └── utils/                      # 历史记录等工具函数
```

---

## 🚀 快速开始

### 环境要求
- Python 3.12+
- uv
- PostgreSQL，并启用 pgvector
- Redis 7+
- Ollama，并准备 `qwen3:8b`、`qwen3:0.6b`、`nomic-embed-text:latest`
- 高德地图 API Key，用于天气与位置工具

### 配置环境变量
在 `Server/ai-service/.env` 中配置本地环境变量：

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=Aura
DB_USER=postgres
DB_PASSWORD=your_password
amap_key=your_amap_key
```

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

data: {"event":"relationship_delta","type":"relationship_delta","relationship_delta":{...}}

data: {"event":"content","type":"content","content":"我在呢"}

data: [DONE]
```

### 本地检查
```bash
python tools/check_mojibake.py
python -m compileall -q app main.py tools
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] FastAPI 应用、生命周期、中间件、CORS 与路由组织
- [x] LangGraph 对话状态机、工具节点和结构化 SSE 事件协议
- [x] PostgreSQL Checkpointer 对话状态持久化
- [x] PGVector 长期记忆保存、检索、分页、清空和删除
- [x] 天气、时间、关系状态、情绪安抚、保存记忆、搜索记忆工具
- [x] 附件、位置、Aura 数据写入、管理端资源和自我更新接口
- [x] SSE 并发上限、队列背压和 `[DONE]` 兼容输出

### 🔜 规划中
- [ ] 补充核心 Agent、记忆和管理端接口测试
- [ ] 完善主动消息调度的可观测性与配置化开关
- [ ] 将更多 Aura 管理能力统一沉淀到 BFF 聚合层
