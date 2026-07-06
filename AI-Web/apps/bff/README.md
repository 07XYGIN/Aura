# Aura BFF

Aura BFF 是 `AI-Web` Monorepo 中的 NestJS 聚合层，位于前端应用与后端服务之间，为 Web、PC、Admin 以及根目录 `app/` Flutter 移动端提供统一 API 入口。

## 当前能力

- 用户接口代理：`/api/user/register`、`/api/user/login`、`/api/user/logout/:userId`、`/api/user/userInfo`、`/api/user/updateInfo`、`/api/user/:username`
- 记忆列表代理：`/api/user/memoryList?page=1&pageSize=10`
- AI 聊天 SSE 代理：`POST /api/chat/sse`
- Bearer Token 鉴权：解析 JWT `sub` 作为用户 ID，并校验 Redis 中的 `token:{userId}`
- 非 SSE 接口统一返回 `{ code, message, data?, token? }`
- 全局异常统一转换为 `{ code, message }`

## SSE 聊天链路

```text
Next.js Web
  -> POST /api/chat/sse
  -> NestJS BFF 注入 userId
  -> FastAPI AI Service /api/send/sse/
  -> LangGraph Agent
  -> BFF 透传 text/event-stream
  -> Web 端增量渲染
```

Flutter 移动端后续也复用同一条 BFF 链路，不直接依赖 Java Core Service 或 Python AI Service。

`/api/chat/sse` 是受保护接口，前端需要携带：

```http
Authorization: Bearer <token>
```

普通 HTTP 接口会被全局响应拦截器包装；SSE 接口直接写入 Express Response，保持流式响应不被 JSON 包装。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `3000` | BFF 服务端口 |
| `JWT_SECRET_KEY` | `change-me-to-a-strong-32-byte-secret-key` | JWT 密钥，需要与 Core Service 一致 |
| `JWT_EXPIRE_TIME` | `86400000` | JWT 过期时间，单位毫秒 |
| `REDIS_HOST` | `localhost` | Redis 主机 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `REDIS_DATABASE` | `0` | Redis DB |
| `REDIS_PASSWORD` | 空 | Redis 密码 |
| `CORE_SERVICE_URL` | `http://127.0.0.1:8080` | Java Core Service 地址 |
| `AI_SERVICE_URL` | `http://127.0.0.1:8000` | Python AI Service 地址 |

## 运行

```bash
cd AI-Web
pnpm install
pnpm dev:bff
```

或：

```bash
pnpm --filter @ai-web/bff start:dev
```

## 构建与检查

```bash
pnpm --filter @ai-web/bff build
pnpm --filter @ai-web/bff lint
pnpm --filter @ai-web/bff format
```
