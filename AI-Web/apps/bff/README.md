# 💖 Aura BFF

<div align="center">

*Aura BFF 是 Aura 的 NestJS 聚合层，位于前端应用与后端服务之间。*
*它统一承接认证、请求代理、响应裁剪和 SSE 转发，让各端不直接暴露内部服务地址。*

---

### 服务端
![NestJS](https://img.shields.io/badge/NestJS-11.x-E0234E?logo=nestjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-18+-5FA04E?logo=nodedotjs&logoColor=white)
![Express](https://img.shields.io/badge/Express-Adapter-000000?logo=express&logoColor=white)

### 代理能力
![Redis](https://img.shields.io/badge/Redis-token--userId-FF4438?logo=redis&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-Guard-000000?logo=jsonwebtokens&logoColor=white)
![SSE](https://img.shields.io/badge/SSE-text%2Fevent--stream-009688)

</div>

---

## 📖 简介

**Aura BFF** 位于 `AI-Web/apps/bff/`，是 `AI-Web` Monorepo 中的 NestJS 聚合层。它为 Web、PC、Admin 以及根目录 `app/` Flutter 移动端提供统一 API 入口。

BFF 负责解析 JWT、校验 Redis 中的 `token:{userId}`、代理 Core Service 与 AI Service 请求，并保持 AI 聊天 SSE 流式响应不被普通 JSON 响应包装破坏。

---

## ✨ 功能介绍

### 🔐 认证与响应治理
- 全局设置 `/api` 前缀
- 支持 Bearer Token 鉴权，解析 JWT `sub` 作为用户 ID
- 校验 Redis 中的 `token:{userId}` 登录态
- 非 SSE 接口统一返回 `{ code, message, data?, token? }`
- 全局异常统一转换为 `{ code, message }`

### 🔁 API 聚合
- 用户接口代理：`/api/user/register`、`/api/user/login`、`/api/user/logout/:userId`、`/api/user/userInfo`、`/api/user/updateInfo`、`/api/user/:username`
- 记忆列表代理：`/api/user/memoryList?page=1&pageSize=10`
- AI 聊天代理：`POST /api/chat/sse`
- 附件上传代理：`POST /api/chat/attachments`
- 位置查询代理：`GET /api/location/adcode`
- Aura 业务代理：`/api/aura/initial-setting`、`/api/aura/relationship`、`/api/aura/memories`、`/api/aura/emotion` 等
- 管理端 Aura 资源代理：`GET /api/admin/aura/:resource`

### 💬 SSE 聊天链路
```text
Next.js Web / Vue PC / Flutter Mobile
  -> POST /api/chat/sse
  -> NestJS BFF 注入 userId 和 token
  -> FastAPI AI Service /api/send/sse/
  -> LangGraph Agent
  -> BFF 透传 text/event-stream
  -> 客户端增量渲染
```

`/api/chat/sse` 是受保护接口，前端需要携带：

```http
Authorization: Bearer <token>
```

普通 HTTP 接口会被全局响应拦截器包装；SSE 接口直接写入 Express Response，保持流式响应。

---

## 🏗️ 技术架构

```text
┌────────────────────────────────────────────────────────┐
│              Web / PC / Admin / Mobile                 │
└──────────────────────────┬─────────────────────────────┘
                           │ /api/*
┌──────────────────────────▼─────────────────────────────┐
│                       Aura BFF                          │
│     AuthGuard · ResponseInterceptor · ExceptionFilter    │
└───────────────┬───────────────────────────┬────────────┘
                │                           │
┌───────────────▼──────────────┐ ┌──────────▼─────────────┐
│        Spring Boot Core       │ │      FastAPI AI Service │
│  /api/user/* · /api/aura/*     │ │  /api/send/sse/ · memory│
└───────────────┬──────────────┘ └──────────┬─────────────┘
                │                           │
┌───────────────▼──────────────┐ ┌──────────▼─────────────┐
│             Redis             │ │ PostgreSQL + pgvector   │
│       token:{userId} 校验      │ │   对话 / 记忆 / Aura 数据│
└──────────────────────────────┘ └────────────────────────┘
```

---

## 📁 仓库结构

```text
apps/bff/
├── src/
│   ├── main.ts                     # NestJS 启动入口与 /api 前缀
│   ├── app.module.ts               # 根模块
│   ├── auth/                       # JWT 工具、鉴权守卫和用户上下文
│   ├── chat/                       # SSE 聊天与附件代理
│   ├── user/                       # 用户接口代理
│   ├── aura/                       # Aura 业务与管理端资源代理
│   ├── location/                   # 高德 adcode 查询代理
│   ├── redis/                      # Redis 连接工具
│   ├── config/                     # 环境变量读取
│   └── common/                     # 装饰器、异常、拦截器和响应工具
├── package.json
├── nest-cli.json
└── tsconfig.json
```

---

## 🚀 快速开始

### 环境要求
- Node.js 18+
- pnpm 10+
- Redis 7+
- `Server/core-service` 默认运行在 `http://127.0.0.1:8080`
- `Server/ai-service` 默认运行在 `http://127.0.0.1:8000`

### 配置环境变量
| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `3001` | BFF 服务端口 |
| `JWT_SECRET_KEY` | `change-me-to-a-strong-32-byte-secret-key` | JWT 密钥，需要与 Core Service 一致 |
| `JWT_EXPIRE_TIME` | `86400000` | JWT 过期时间，单位毫秒 |
| `REDIS_HOST` | `localhost` | Redis 主机 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `REDIS_DATABASE` | `0` | Redis DB |
| `REDIS_PASSWORD` | 空 | Redis 密码 |
| `CORE_SERVICE_URL` | `http://127.0.0.1:8080` | Java Core Service 地址 |
| `AI_SERVICE_URL` | `http://127.0.0.1:8000` | Python AI Service 地址 |
| `AMAP_KEY` / `amap_key` | 空 | 高德地图 API Key |

### 启动 BFF 聚合层
```bash
cd AI-Web
pnpm install
pnpm dev:bff
```

也可以直接过滤当前包：

```bash
pnpm --filter @ai-web/bff start:dev
```

服务默认运行在：

```text
http://127.0.0.1:3001/api
```

### 构建与检查
```bash
pnpm --filter @ai-web/bff build
pnpm --filter @ai-web/bff lint
pnpm --filter @ai-web/bff format
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] NestJS BFF 工程与 `/api` 全局前缀
- [x] JWT + Redis 登录态鉴权守卫
- [x] 用户注册、登录、资料、退出和删除接口代理
- [x] AI 聊天 SSE 代理与 `text/event-stream` 透传
- [x] 附件、位置、Aura 业务和管理端资源代理
- [x] 统一响应拦截器与全局异常过滤器
- [x] `.env` 本地加载与服务地址配置

### 🔜 规划中
- [ ] 补充 BFF 控制器和服务层测试
- [ ] 统一 Admin 的管理接口入口
- [ ] 增加请求日志、链路追踪和限流策略
