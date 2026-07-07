# 💖 Aura PC

<div align="center">

*Aura PC 是 Aura 的 Vue 3 桌面端聊天客户端，承担聊天、记忆、设置和登录注册等核心使用场景。*
*它通过 BFF 接入统一认证与 SSE 对话链路，提供更接近桌面工作台的陪伴体验。*

---

### 客户端
![Vue.js](https://img.shields.io/badge/Vue.js-3.x-4FC08D?logo=vuedotjs&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-7.x-646CFF?logo=vite&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4.x-06B6D4?logo=tailwindcss&logoColor=white)

### 状态与 UI
![Pinia](https://img.shields.io/badge/Pinia-State-FFD859)
![Vue Router](https://img.shields.io/badge/Vue_Router-4.x-4FC08D)
![reka-ui](https://img.shields.io/badge/reka--ui-Components-111827)
![SSE](https://img.shields.io/badge/SSE-fetch--event--source-009688)

</div>

---

## 📖 简介

**Aura PC** 位于 `AI-Web/apps/PC/`，是 Aura 项目的 Vue 3 + Vite 桌面端客户端。它包含聊天、记忆、设置、用户、登录和注册等页面，并通过 `AI-Web/apps/bff` 统一访问后端 API。

移动端已迁移为仓库根目录 `app/` 下的 Flutter 工程，不再属于 `AI-Web` pnpm workspace。

---

## ✨ 功能介绍

### 💬 聊天客户端
- 提供左侧导航与桌面端主布局
- 提供聊天页面与 SSE 客户端封装
- 默认通过 `VITE_BFF_URL` 请求 `/api/chat/sse`
- 支持历史消息读取和消息渲染
- 集成 Markdown、代码高亮和 Mermaid 渲染依赖

### 🔐 认证与用户状态
- 提供登录和注册页面
- 使用 Pinia 存储 token
- Axios 请求封装自动注入 `Authorization: Bearer <token>`
- 401 响应会清理登录态并跳转登录页

### 🧭 页面与 UI
- 提供记忆列表页面
- 提供设置页面与主题切换入口
- 使用 shadcn-vue 风格组件、reka-ui、lucide-vue-next 和 Tailwind CSS
- 页面组件与通用 UI 组件分层组织

---

## 🏗️ 技术架构

```text
┌────────────────────────────────────────────────────────┐
│                     Vue 3 PC App                       │
│        Sidebar · Chat · Memory · Setting · Auth         │
└──────────────────────────┬─────────────────────────────┘
                           │ Axios / fetch-event-source
┌──────────────────────────▼─────────────────────────────┐
│                    Client Runtime                       │
│        Pinia token · request.ts · useSse.ts              │
└──────────────────────────┬─────────────────────────────┘
                           │ VITE_BFF_URL
┌──────────────────────────▼─────────────────────────────┐
│                    NestJS BFF 层                         │
│              /api/chat/sse · /api/user/* · /api/aura/*   │
└───────────────┬───────────────────────────┬────────────┘
                │                           │
┌───────────────▼──────────────┐ ┌──────────▼─────────────┐
│        Spring Boot Core       │ │      FastAPI AI Service │
│       认证 / 用户 / Aura       │ │       对话 / 记忆 / SSE  │
└──────────────────────────────┘ └────────────────────────┘
```

---

## 📁 仓库结构

```text
apps/PC/
├── src/
│   ├── api/                        # 登录、消息和用户接口
│   ├── components/
│   │   ├── pages/                  # Sidebar、LoginForm、MemoryList 等页面组件
│   │   └── ui/                     # 通用 UI 组件
│   ├── lib/                        # 通用工具
│   ├── pages/                      # 路由页面：chat、Memory、Setting、Login、register
│   ├── router/                     # Vue Router 与鉴权跳转
│   ├── store/                      # Pinia 状态
│   ├── utils/                      # request 与 SSE 工具
│   ├── App.vue
│   └── main.ts
├── package.json
└── vite.config.ts
```

---

## 🚀 快速开始

### 环境要求
- Node.js 18+
- pnpm 10+
- BFF 默认运行在 `http://127.0.0.1:3001`

### 配置环境变量
```dotenv
VITE_BFF_URL=http://127.0.0.1:3001
```

### 启动 PC 客户端
```bash
cd AI-Web
pnpm install
pnpm --filter @ai-web/pc dev
```

### 构建
```bash
pnpm --filter @ai-web/pc build
```

### 格式化
```bash
pnpm --filter @ai-web/pc format
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] Vue 3 + Vite + Tailwind CSS PC 客户端工程
- [x] 左侧导航、主布局、聊天、记忆、设置、登录和注册页面
- [x] Pinia token 状态、Axios 请求封装和 401 跳转登录
- [x] BFF `/api/chat/sse` 默认请求链路
- [x] SSE 客户端工具、Markdown、代码高亮和 Mermaid 依赖接入
- [x] shadcn-vue 风格通用 UI 组件目录

### 🔜 规划中
- [ ] 打通完整 AI Service SSE 聊天闭环
- [ ] 接入真实记忆列表和删除接口
- [ ] 统一登录态、错误提示和空状态
- [ ] 优化聊天消息渲染和 Markdown 展示
- [ ] 补充基础页面测试
