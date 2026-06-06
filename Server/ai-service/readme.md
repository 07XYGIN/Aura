# 💖 Aura AI Service

<div align="center">

*Aura 的 AI 对话服务，负责 LangGraph 编排、SSE 流式输出、工具调用、长期记忆和聊天历史。*

---

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.127+-009688?logo=fastapi&logoColor=white)
![Uvicorn](https://img.shields.io/badge/Uvicorn-0.40+-499848)
![LangGraph](https://img.shields.io/badge/LangGraph-1.x-1C3C3C?logo=langchain&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1.x-1C3C3C?logo=langchain&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Qwen3-000000?logo=ollama&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)

</div>

---

## 📖 简介

**AI Service** 是 Aura 的 FastAPI 异步 AI 服务。它通过 LangGraph 构建对话状态机，使用 Ollama 本地模型处理多轮对话，并将响应以 Server-Sent Events（SSE）形式返回客户端。服务同时负责用户注册/登录、聊天历史读取、长期记忆写入与语义检索。

---

## ✨ 功能介绍

### 🤖 AI 对话
- 基于 LangGraph `StateGraph` 编排聊天节点与工具节点
- 使用 `qwen3:8b` 作为主要对话模型
- 支持天气查询、记忆保存、记忆搜索等工具调用
- 使用 PostgreSQL Checkpointer 持久化对话状态
- `/api/send/sse/` 通过 SSE 持续输出模型响应片段

### 🧠 记忆系统
- `save_memory_tool` 分析用户消息并抽取值得长期保存的信息
- `search_memory_tool` 按用户隔离检索历史记忆
- `PGVector` + PostgreSQL/pgvector 存储语义向量
- `nomic-embed-text:latest` 用于记忆 Embedding
- 记忆 metadata 包含 `user_id`、`title`、`create_time`

### 👤 用户与历史
- 邀请码注册与登录校验
- Passlib/bcrypt 密码哈希
- 按 `code` 请求头查询用户信息
- 按 `userId` 查询或清空聊天历史
- 统一成功响应与自定义异常处理

### 🔌 API 端点

| 方法 | 端点 | 功能 |
|------|------|------|
| POST | `/api/register` | 用户注册 |
| POST | `/api/login` | 用户登录 |
| GET | `/api/user/info` | 根据 `code` Header 获取用户信息 |
| DELETE | `/api/user/logout?userid={uuid}` | 删除账户 |
| POST | `/api/send/sse/` | 发送消息并返回 SSE 流式响应 |
| GET | `/api/history/{userId}` | 获取指定用户聊天历史 |
| DELETE | `/api/history/{userId}` | 清空指定用户聊天历史 |

---

## 🏗️ 技术架构

```
┌──────────────────────────────┐
│       Web / PC / BFF          │
└───────────────┬──────────────┘
                │ HTTP / SSE
┌───────────────▼──────────────┐
│            FastAPI            │
│ login / user / msg / history  │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│          LangGraph            │
│     chat node ↔ tool node      │
└───────┬──────────────┬───────┘
        │              │
┌───────▼───────┐ ┌────▼──────────────────┐
│ ChatOllama     │ │ Tools                 │
│ qwen3:8b       │ │ weather / memory      │
└───────┬───────┘ └────┬──────────────────┘
        │              │
┌───────▼──────────────▼──────┐
│ PostgreSQL + pgvector        │
│ Checkpoint / User / Memory   │
└──────────────────────────────┘
```

---

## 📁 项目结构

```
ai-service/
├── main.py                              # FastAPI 应用入口与生命周期
├── pyproject.toml                       # uv / Python 项目依赖
├── uv.lock                              # 锁定依赖版本
├── app/
│   ├── core/
│   │   └── agent/
│   │       ├── agent_graph.py           # LangGraph 工作流
│   │       ├── prompt.py                # 系统提示词与记忆提示词
│   │       └── tools/                   # 天气、记忆等工具
│   ├── routers/
│   │   ├── msg.py                       # SSE 消息接口
│   │   └── ...
│   ├── schemas/                         # 请求、响应、记忆模型
│   └── ...
└── ...
```

---

## 🚀 快速开始

### 环境要求
- Python 3.12+
- uv
- PostgreSQL，并启用 pgvector
- Ollama，本地准备 `qwen3:8b`、`qwen3:0.6b`、`nomic-embed-text:latest`
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

服务默认运行在 `http://127.0.0.1:8000`。`main.py` 中的 CORS 当前放行 `http://localhost:5173`，用于本地前端联调。

### 调试接口

```bash
curl -N -X POST http://127.0.0.1:8000/api/send/sse/ \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"你好，Aura\",\"userId\":\"demo-user\"}"
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] FastAPI 应用工厂、生命周期与路由组织
- [x] 用户注册、登录、用户信息、注销接口
- [x] LangGraph 对话状态机与工具节点
- [x] SSE 流式响应接口
- [x] PostgreSQL Checkpointer 对话状态持久化
- [x] PGVector 长期记忆保存与检索
- [x] 天气工具、高德 API 接入
- [x] 自定义异常与请求参数校验处理

### 🔨 进行中
- [ ] 前端登录态与 AI 服务用户体系打通
- [ ] 记忆列表、记忆删除等管理接口恢复
- [ ] 流式响应的端到端客户端渲染
- [ ] Docker Compose 与数据库初始化脚本
- [ ] 测试用例与生产部署配置
