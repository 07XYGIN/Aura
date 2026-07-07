# 💖 Aura Web

<div align="center">

*Aura Web 是 Aura 的 Next.js 用户工作台，承载聊天、记忆、设置和认证等核心使用场景。*
*它通过 BFF 聚合层接入后端能力，并以流式 UI 呈现 Aura 的实时陪伴体验。*

---

### 客户端
![Next.js](https://img.shields.io/badge/Next.js-16.x-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19.x-61DAFB?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4.x-06B6D4?logo=tailwindcss&logoColor=white)

### 状态与 UI
![Zustand](https://img.shields.io/badge/Zustand-State-764ABC)
![shadcn/ui](https://img.shields.io/badge/shadcn%2Fui-Radix-000000)
![lucide-react](https://img.shields.io/badge/lucide-react-F56565)

</div>

---

## 📖 简介

**Aura Web** 位于 `AI-Web/apps/web/`，是 Aura 项目的 Next.js + React 用户端。它面向 AI 陪伴、聊天、记忆、设置和认证流程，并通过 `AI-Web/apps/bff` 访问统一后端 API。

移动端已迁移为仓库根目录 `app/` 下的 Flutter 工程，不再属于 `AI-Web` pnpm workspace。

---

## ✨ 功能介绍

### 💬 AI 聊天工作台
- 提供 Aura 聊天主界面和应用外壳
- 通过 BFF `/api/chat/sse` 接入 AI 流式对话
- 支持 SSE 文本分片增量渲染
- 展示情绪状态、记忆候选和关系变化等 metadata
- 支持附件选择与语音输入入口

### 🔐 认证与用户状态
- 提供登录与注册页面
- 使用 Zustand 存储登录态与 token
- 请求封装自动注入 `Authorization: Bearer <token>`
- 401 响应会清理本地登录态并跳转登录页

### 🧭 页面与体验
- 提供聊天、记忆、设置等基础页面
- 使用 `next-themes` 支持主题切换
- 使用 route transition 组件处理页面过渡
- 使用 sonner 统一展示关键错误提示

---

## 🏗️ 技术架构

```text
┌────────────────────────────────────────────────────────┐
│                   Next.js App Router                   │
│        chat · memories · settings · login · layout      │
└──────────────────────────┬─────────────────────────────┘
                           │ fetch / SSE
┌──────────────────────────▼─────────────────────────────┐
│                     Web Runtime                         │
│       Zustand token · request.ts · current-user          │
└──────────────────────────┬─────────────────────────────┘
                           │ NEXT_PUBLIC_BFF_URL
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
apps/web/
├── app/
│   ├── chat/                       # 聊天页面
│   ├── login/                      # 登录页面
│   ├── memories/                   # 记忆页面
│   ├── settings/                   # 设置页面
│   ├── globals.css                 # Tailwind 与全局样式
│   └── layout.tsx                  # 应用根布局
├── components/
│   ├── arua/                       # Aura 应用壳、聊天、记忆和设置组件
│   ├── login/                      # 登录表单组件
│   └── ui/                         # shadcn/ui 基础组件
├── lib/
│   ├── request.ts                  # BFF 请求封装
│   ├── auth-token.ts               # token 工具
│   ├── current-user.ts             # 当前用户工具
│   └── utils.ts                    # 通用工具函数
├── package.json
└── next.config.ts
```

---

## 🚀 快速开始

### 环境要求
- Node.js 18+
- pnpm 10+
- BFF 默认运行在 `http://127.0.0.1:3001`

### 配置环境变量
本地联调 BFF 时可配置：

```dotenv
NEXT_PUBLIC_BFF_URL=http://127.0.0.1:3001
NEXT_PUBLIC_API_URL=http://127.0.0.1:3001
```

聊天页优先读取 `NEXT_PUBLIC_BFF_URL`，缺省时使用 `NEXT_PUBLIC_API_URL`，最终请求：

```text
POST /api/chat/sse
```

### 启动 Web 工作台
```bash
cd AI-Web
pnpm install
pnpm dev:web
```

也可以直接过滤当前包：

```bash
pnpm --filter @ai-web/web dev
```

Next.js 默认运行在：

```text
http://localhost:3000
```

### 构建
```bash
pnpm --filter @ai-web/web build
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] Next.js 16 + React 19 工作台工程搭建
- [x] 登录 / 注册页面和 Zustand token 存储
- [x] BFF SSE 流式对话接入
- [x] 聊天流式文本增量渲染
- [x] 情绪状态、记忆候选和关系变化 metadata 展示
- [x] 记忆页、设置页、主题切换和路由过渡
- [x] 附件选择与语音输入入口

### 🔜 规划中
- [ ] 抽离 `useChatStream`、`useAutoScroll`、`useVoiceInput`
- [ ] 接入长期记忆列表和用户资料接口
- [ ] 补充核心交互测试
