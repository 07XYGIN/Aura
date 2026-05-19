# AI Service - AI 对话服务

FastAPI 异步 Web 框架构建的 AI 对话代理服务，集成 LangGraph 工作流编排、持久化记忆系统和多用户支持。

## 技术栈

### 框架与服务器
- **FastAPI** 0.127.0 - 现代异步 Web 框架
- **Uvicorn** 0.40.0 - ASGI 服务器
- **Starlette** 0.50.0 - Web 框架基础

### AI/LLM
- **LangGraph** - 代理工作流编排与状态管理
- **LangChain** - LLM 框架与工具集成
- **ChatOllama** - 本地 LLM 集成（Qwen 3 8B 用于对话，0.6B 用于记忆）
- **Sentence Transformers** - 语义记忆嵌入

### 数据库
- **PostgreSQL** - 主数据存储，支持异步操作
- **SQLAlchemy 2.0** - 异步 ORM
- **asyncpg** 0.31.0 - 异步 PostgreSQL 驱动
- **pgvector** 0.3.6 - 向量存储扩展

### 安全与工具库
- **Passlib** 1.7.4 + **bcrypt** 5.0.0 - 密码哈希
- **python-dotenv** - 环境配置
- **Pydantic** - 数据验证

## 已实现功能

### 1. 用户认证与管理
- 邀请码验证的用户注册
- bcrypt 密码加密的安全登录
- 用户信息查询（创建时间、ID、用户名）
- 账户删除/登出

### 2. 对话 AI 代理
- 基于 LangGraph 状态机的多轮对话
- 工具调用能力（外部集成）
- 系统提示词驱动的行为
- 通过 Server-Sent Events (SSE) 流式响应

### 3. 记忆系统
- 自动提取和存储重要用户信息
- 基于向量的语义记忆检索
- 用户隔离的记忆存储
- 双模型方案：主模型用于对话，小模型用于记忆提取

### 4. 工具集成
- **天气工具** - 通过高德地图 API 获取实时天气
- **记忆工具** - 保存和搜索用户记忆
- 可扩展的工具框架

### 5. 聊天历史
- PostgreSQL 支持的对话持久化
- 用户隔离的线程管理
- 历史记录查询和删除接口
- 自动状态检查点

### 6. API 端点

| 方法 | 端点 | 功能 |
|------|------|------|
| POST | `/api/register` | 用户注册 |
| POST | `/api/login` | 用户登录 |
| GET | `/api/user/info` | 获取用户信息 |
| DELETE | `/api/user/logout` | 账户删除 |
| POST | `/api/send/sse/` | 发送消息（流式响应） |
| GET | `/api/history/{userId}` | 获取聊天历史 |
| DELETE | `/api/history/{userId}` | 清空聊天历史 |

## 项目结构

```
ai-service/
├── main.py                          # FastAPI 应用入口
├── app/
│   ├── core/
│   │   ├── agent/
│   │   │   ├── agent_graph.py      # LangGraph 工作流定义
│   │   │   ├── prompt.py           # 系统提示词
│   │   │   └── tools/              # 工具实现
│   │   │       ├── memery.py       # 记忆保存工具
│   │   │       ├── search_memery.py # 记忆搜索工具
│   │   │       └── term_memory.py  # 记忆管理
│   │   └── config.py               # 配置（LLM、数据库、API 密钥）
│   ├── model/
│   │   └── User.py                 # 用户数据库模型
│   ├── schemas/
│   │   └── momery.py               # 记忆数据模式
│   └── routers/
│       ├── login.py                # 认证端点
│       ├── user.py                 # 用户管理端点
│       ├── msg.py                  # 消息处理端点
│       └── history.py              # 聊天历史端点
└── requirements.txt                # Python 依赖
```

## 快速开始

### 前置条件
- Python 3.8+
- PostgreSQL
- Ollama（含 Qwen 模型）

### 安装

```bash
pip install -r requirements.txt
```

### 配置

创建 `.env` 文件：
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost/ai_service
AMAP_API_KEY=your_amap_api_key
```

### 运行

```bash
uvicorn main:app --reload
```

服务运行在 `http://localhost:8000`

## 核心工作流

1. 用户通过 `/api/send/sse/` 发送消息
2. LangGraph 路由到聊天节点
3. LLM 使用系统提示词和可用工具处理消息
4. 如需工具调用，路由到工具节点执行
5. 工具结果反馈给 LLM
6. 响应通过 SSE 流式返回客户端
7. 对话状态持久化到 PostgreSQL
8. 重要信息自动提取并存储到记忆系统

## 数据持久化

- **用户数据**：PostgreSQL User 表
- **对话状态**：PostgreSQL + LangGraph 检查点
- **记忆向量**：PostgreSQL + pgvector 扩展
- **用户隔离**：thread_id = userId 用于状态管理
