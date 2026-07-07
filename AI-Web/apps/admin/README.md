# 💖 Aura Admin

<div align="center">

*Aura Admin 是 Aura 的 Vue 3 管理后台，负责用户资料、记忆、人格、关系和情绪等运营管理能力。*
*它面向后台操作场景，优先提供可检索、可审阅、可治理的 Aura 数据工作台。*

---

### 客户端
![Vue.js](https://img.shields.io/badge/Vue.js-3.x-4FC08D?logo=vuedotjs&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-7.x-646CFF?logo=vite&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![Element Plus](https://img.shields.io/badge/Element_Plus-2.x-409EFF?logo=element&logoColor=white)

### 状态与请求
![Pinia](https://img.shields.io/badge/Pinia-State-FFD859)
![Vue Router](https://img.shields.io/badge/Vue_Router-5.x-4FC08D)
![Axios](https://img.shields.io/badge/Axios-HTTP-5A29E4?logo=axios&logoColor=white)

</div>

---

## 📖 简介

**Aura Admin** 位于 `AI-Web/apps/admin/`，是 Aura 项目的 Vue 3 管理后台。它承载登录注册、用户资料、长期记忆、人格配置、关系状态、会话消息、情绪快照、自我更新和记忆合并等管理场景。

当前请求封装默认通过 `VITE_AI_SERVICE_URL` 访问 AI Service 管理端点，后续可逐步统一切换到 `AI-Web/apps/bff` 聚合层。

---

## ✨ 功能介绍

### 🗂️ 管理后台基础
- Vue 3 + Vite + Element Plus 管理端界面
- 登录、注册、后台布局、用户信息页和首页
- 路由守卫与登录态判断
- Pinia 用户状态持久化
- Axios 请求封装、token 注入、401 跳转登录页

### 🧠 Aura 数据管理
- 长期记忆管理与记忆合并候选处理
- 用户画像与人格配置查看
- 关系状态、会话消息和情绪快照资源页
- 自我更新列表、创建、状态调整和删除
- 通用只读资源页支持管理端资源扩展

### 🔌 当前页面路由
| 路径 | 功能 |
| --- | --- |
| `/` | 后台首页 |
| `/user/userInfo` | 用户信息 |
| `/memory` | 记忆管理 |
| `/aura/profiles` | Aura 用户画像 |
| `/aura/personas` | 人格配置 |
| `/aura/relationships` | 关系状态 |
| `/aura/messages` | 会话消息 |
| `/aura/emotions` | 情绪快照 |
| `/aura/memories` | 长期记忆 |
| `/aura/self-updates` | 自我更新 |
| `/aura/memory-merge` | 记忆合并 |

---

## 🏗️ 技术架构

```text
┌────────────────────────────────────────────────────────┐
│                   Vue 3 Admin App                      │
│      Layout · Router Guard · Pinia Store · Element UI   │
└──────────────────────────┬─────────────────────────────┘
                           │ Axios + Bearer Token
┌──────────────────────────▼─────────────────────────────┐
│                  Request Runtime                        │
│        VITE_AI_SERVICE_URL · 401 redirect · ElMessage    │
└──────────────────────────┬─────────────────────────────┘
                           │ 当前默认直连
┌──────────────────────────▼─────────────────────────────┐
│                  FastAPI AI Service                     │
│       /api/admin/* · /api/memory/* · /api/user/*         │
└──────────────────────────┬─────────────────────────────┘
                           │ 后续统一收敛
┌──────────────────────────▼─────────────────────────────┐
│                    NestJS BFF 层                         │
│                管理 API 聚合 · 鉴权 · 响应裁剪             │
└────────────────────────────────────────────────────────┘
```

---

## 📁 仓库结构

```text
apps/admin/
├── src/
│   ├── api/                        # 用户、记忆、Aura、自我更新接口
│   ├── pages/
│   │   ├── aura/                   # Persona、Memory、Emotion、Relationship 等管理页
│   │   ├── home/                   # 首页
│   │   ├── layout/                 # 后台布局
│   │   ├── login/                  # 登录页
│   │   ├── memory/                 # 记忆管理页
│   │   ├── register/               # 注册页
│   │   └── user/                   # 用户信息页
│   ├── router/                     # Vue Router 与路由守卫
│   ├── store/                      # Pinia 状态
│   ├── type/                       # 前端类型
│   ├── utils/                      # Axios 请求封装
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
- AI Service 默认运行在 `http://localhost:8000`

### 配置环境变量
```dotenv
VITE_AI_SERVICE_URL=http://localhost:8000
```

### 启动管理后台
```bash
cd AI-Web
pnpm install
pnpm dev:admin
```

也可以直接过滤当前包：

```bash
pnpm --filter @ai-web/admin dev
```

### 构建
```bash
pnpm --filter @ai-web/admin build
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] Vue 3 + Vite + Element Plus 管理后台工程
- [x] 登录、注册、后台布局、用户信息和首页
- [x] 路由守卫、Pinia 登录态和 Axios token 注入
- [x] 记忆管理、长期记忆和记忆合并页面
- [x] Aura 用户画像、人格配置、关系、消息、情绪和自我更新页面
- [x] 401 统一跳转登录页与 Element Plus 错误提示

### 🔜 规划中
- [ ] 统一切换管理接口到 BFF 聚合层
- [ ] 补充用户管理列表、数据看板和操作审计
- [ ] 补充更完整的表单校验、空状态和错误提示
