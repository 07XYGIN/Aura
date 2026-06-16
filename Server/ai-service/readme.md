# Aura AI Service

Aura 的 Python AI 对话服务，负责 LangGraph 编排、SSE 流式输出、工具调用、长期记忆和聊天历史。

## 简介

AI Service 是 Aura 的 FastAPI 异步 AI 服务。它通过 LangGraph 构建对话状态机，使用 Ollama 本地模型处理多轮对话，并将响应以 Server-Sent Events（SSE）的形式返回客户端。服务同时提供聊天历史读取、长期记忆写入与语义检索能力。

## 功能

### AI 对话

- 基于 LangGraph `StateGraph` 编排聊天节点与工具节点。
- 使用 `qwen3:8b` 作为主要对话模型。
- `/api/send/sse/` 通过 SSE 持续输出模型响应片段。
- SSE 协议保持 `data: JSON` + `data: [DONE]` 兼容；每轮会输出 `emotion`、`memory_candidate`、`relationship_delta` 和多段 `content` 事件。
- `content` 事件保留顶层 `content` 字段，旧前端仍可按原方式消费正文片段。

### 工具调用

- `get_weather`：查询天气，当前默认北京，高德接口不可用时不会编造结果。
- `save_memory_tool`：分析用户消息，将值得长期保存的信息写入记忆库。
- `search_memory_tool`：按用户隔离检索历史记忆。
- `get_current_datetime`：返回指定时区的当前日期、时间和星期。
- `get_relationship_status`：基于当前消息的规则估算关系状态和亲密度，不依赖新数据库表。
- `get_emotional_support_advice`：根据用户情绪给出安抚策略和回复方向。
- `tools/check_mojibake.py`：无依赖本地检查脚本，用于扫描 ai-service 源码中的常见中文乱码特征。

### 记忆系统

- `PGVector` + PostgreSQL/pgvector 存储语义向量。
- `nomic-embed-text:latest` 用于记忆 Embedding。
- 记忆 metadata 包含 `user_id`、`title`、`create_time`。

### API 端点

| 方法 | 端点 | 功能 |
| --- | --- | --- |
| POST | `/api/send/sse/` | 发送消息并返回 SSE 流式响应 |
| GET | `/api/history/{userId}` | 获取指定用户聊天历史 |
| DELETE | `/api/history/{userId}` | 清空指定用户聊天历史 |
| GET | `/api/memory/list` | 分页获取指定用户记忆 |
| GET | `/api/memory/getMemory` | 检索指定用户记忆 |

## 项目结构

```text
ai-service/
├── main.py
├── pyproject.toml
├── uv.lock
└── app/
    ├── core/
    │   ├── agent/
    │   │   ├── agent_graph.py
    │   │   ├── prompt.py
    │   │   └── tools/
    │   ├── config.py
    │   ├── emotion.py
    │   └── exceptions.py
    ├── routers/
    ├── schemas/
    ├── utils/
    └── tools/
```

## 快速开始

### 环境要求

- Python 3.12+
- uv
- PostgreSQL，并启用 pgvector
- Ollama，本地准备 `qwen3:8b` 和 `nomic-embed-text:latest`
- 高德地图 API Key，用于天气工具

### 配置

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

### 运行

```bash
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

服务默认运行在 `http://127.0.0.1:8000`。

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

## 当前状态

- 已完成 FastAPI 应用、生命周期与路由组织。
- 已完成 LangGraph 对话状态机与工具节点。
- 已完成 SSE 流式响应接口。
- 已完成 PostgreSQL Checkpointer 对话状态持久化。
- 已完成 PGVector 长期记忆保存与检索。
- 已接入天气、时间、关系状态、情绪安抚、保存记忆、搜索记忆工具。
- 已强化 SSE 结构化事件协议，并保留前端现有 `data.content` 与 `[DONE]` 消费方式。
