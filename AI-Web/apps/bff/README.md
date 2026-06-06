# 💖 Aura BFF

<div align="center">

*Aura 的 Backend For Frontend 聚合层骨架，后续用于统一承接多端请求。*

---

![NestJS](https://img.shields.io/badge/NestJS-11.x-E0234E?logo=nestjs&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-18+-339933?logo=nodedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6?logo=typescript&logoColor=white)
![RxJS](https://img.shields.io/badge/RxJS-7.x-B7178C?logo=reactivex&logoColor=white)

</div>

---

## 📖 简介

**Aura BFF** 是 `AI-Web` Monorepo 下的 NestJS 服务，定位为前端应用与后端微服务之间的请求聚合层。当前已经删除 NestJS 默认 Controller、Service、单元测试和 e2e 模板，只保留可启动的基础骨架：`main.ts` 与空的 `AppModule`。

---

## ✨ 功能介绍

### ✅ 当前能力
- NestJS 应用入口保留在 `src/main.ts`
- `AppModule` 保留为空模块，便于后续按业务拆分模块
- 支持开发启动、生产构建、格式化和 lint
- 默认不再提供 `GET /` 模板接口

### 🧩 目标职责
- 为 Web / PC / Admin / Mobile 提供统一 API 前缀
- 聚合 `core-service` 的用户认证与资料接口
- 代理 `ai-service` 的 SSE 流式对话接口
- 统一处理 token、错误响应、DTO 和接口版本
- 面向不同客户端裁剪响应结构，减少前端重复适配

---

## 🏗️ 技术架构

```
┌──────────────────────────────────────┐
│ Web / PC / Admin / Mobile             │
└──────────────────┬───────────────────┘
                   │ HTTP / SSE
┌──────────────────▼───────────────────┐
│              NestJS BFF               │
│       main.ts + AppModule skeleton    │
└──────────────┬────────────────┬──────┘
               │                │
┌──────────────▼────────┐ ┌─────▼────────────────┐
│ Spring Boot Core       │ │ FastAPI AI Service    │
│ 用户认证 / 用户资料     │ │ AI 对话 / 记忆 / 历史  │
└───────────────────────┘ └──────────────────────┘
```

---

## 📁 项目结构

```
apps/bff/
├── src/
│   ├── main.ts                    # Nest 应用启动入口
│   └── app.module.ts              # 空根模块骨架
├── package.json
├── nest-cli.json
└── ...
```

---

## 🚀 快速开始

### 环境要求
- Node.js 18+
- pnpm 10+

### 安装依赖

```bash
cd AI-Web
pnpm install
```

### 运行开发服务

```bash
pnpm dev:bff
```

或直接过滤当前包：

```bash
pnpm --filter @ai-web/bff start:dev
```

服务默认监听 `http://localhost:3000`，也可以通过 `PORT` 环境变量修改端口。

### 构建与检查

```bash
pnpm --filter @ai-web/bff build
pnpm --filter @ai-web/bff lint
pnpm --filter @ai-web/bff format
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] NestJS 11 基础工程搭建
- [x] 默认 Controller / Service / 测试模板删除
- [x] 保留 `main.ts` 与空 `AppModule` 骨架
- [x] Monorepo workspace 包接入

### 🔨 进行中
- [ ] 设计 BFF API 前缀与模块拆分
- [ ] 代理 Core Service 用户认证与用户资料接口
- [ ] 代理 AI Service SSE 对话接口
- [ ] 增加鉴权 Guard、DTO、统一错误响应
- [ ] 增加生产部署配置
