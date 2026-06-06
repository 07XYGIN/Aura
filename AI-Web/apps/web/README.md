# 💖 Aura Web

<div align="center">

*Aura 的新版 Web 工作台，面向桌面端聊天、记忆查看、个人设置与认证流程。*

---

![Next.js](https://img.shields.io/badge/Next.js-16.2.6-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19.2.4-61DAFB?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4.x-06B6D4?logo=tailwindcss&logoColor=white)
![Radix UI](https://img.shields.io/badge/Radix_UI-1.x-161618?logo=radixui&logoColor=white)
![Lucide](https://img.shields.io/badge/Lucide-icons-F56565)

</div>

---

## 📖 简介

**Aura Web** 是 `AI-Web` Monorepo 下的 Next.js 客户端应用，使用 React 19、Tailwind CSS 4、Radix UI、lucide-react 和 shadcn 风格组件构建。当前应用已经包含聊天主界面、登录/注册页面、记忆页、设置页、主题切换和请求封装，是 Aura 桌面端体验的新版本。

---

## ✨ 功能介绍

### 💬 聊天工作台
- 支持本地消息列表、输入框、图片附件选择与附件名展示
- 支持浏览器语音识别输入，默认语言为 `zh-CN`
- 消息提交目前先进入本地状态，后续接入 AI 服务 SSE 流式响应

### 🔐 登录与注册
- `/login` 提供登录/注册双模式表单
- 表单包含用户名、密码、邮箱、年龄、性别等字段
- `lib/request.ts` 统一封装 `fetch`、Bearer Token、401 跳转和错误提示
- `NEXT_PUBLIC_API_URL` 指向后端基础地址，当前本地默认 `http://localhost:8080`

### 🧠 记忆与设置
- `/memories` 提供长期记忆工作区的占位布局
- `/settings` 提供用户资料、语言、主题、安全操作等设置布局

### 🎨 体验与组件
- `AruaAppShell` 统一导航、侧栏、账户概览和页面容器
- `next-themes` 提供主题切换能力
- React View Transition 组织页面切换动画
- `sonner` 提供全局 Toast 提示

---

## 🏗️ 技术架构

```
┌──────────────────────────────┐
│          Next.js App          │
│  app/page / login / memories  │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│        Aura UI Layer          │
│ AppShell / Chat / Settings    │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│       Request Adapter         │
│ NEXT_PUBLIC_API_URL + token   │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│ Core Service / AI Service     │
│ 登录注册 / 用户资料 / SSE 对话 │
└──────────────────────────────┘
```

---

## 📁 项目结构

```
apps/web/
├── app/
│   ├── page.tsx                    # 聊天首页
│   ├── login/page.tsx              # 登录/注册页
│   ├── layout.tsx                  # 全局布局与 ThemeProvider
│   └── ...
├── components/
│   ├── arua/                       # Aura 工作台业务组件
│   └── ui/                         # 通用 UI 组件
├── lib/
│   ├── request.ts                  # fetch 封装
│   └── ...
├── types/                          # API、认证、UI 类型
├── package.json
└── ...
```

---

## 🚀 快速开始

### 环境要求
- Node.js 18+
- pnpm 10+
- Core Service 默认运行在 `http://localhost:8080`

### 配置

本地环境变量位于 `apps/web/.env`：

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8080
```

如果通过 BFF 转发请求，可将该值改为 BFF 地址。

### 安装依赖

```bash
cd AI-Web
pnpm install
```

### 运行

```bash
pnpm dev:web
```

或直接过滤当前包：

```bash
pnpm --filter @ai-web/web dev
```

应用默认运行在 `http://localhost:3000`。

### 构建与检查

```bash
pnpm --filter @ai-web/web build
pnpm --filter @ai-web/web lint
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] Next.js 16 + React 19 应用搭建
- [x] Aura 工作台侧栏、导航和基础布局
- [x] 聊天页面本地交互、附件选择、语音输入
- [x] 登录/注册表单与请求封装
- [x] 记忆页、设置页和主题切换
- [x] 通用 UI 组件与 Toast 提示接入

### 🔨 进行中
- [ ] 登录/注册接口的完整联调和 token 存储
- [ ] 聊天消息接入 AI Service SSE 流式响应
- [ ] 记忆列表、用户资料和设置项接入真实数据
- [ ] 统一走 BFF 的 API 路由规划
- [ ] 页面级测试与端到端交互测试
