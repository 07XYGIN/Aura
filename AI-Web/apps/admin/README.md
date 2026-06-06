# 💖 Aura Admin

<div align="center">

*Aura 的 Vue3 管理后台，当前聚焦登录注册、用户资料和基础工作台。*

---

![Vue.js](https://img.shields.io/badge/Vue.js-3.5+-4FC08D?logo=vuedotjs&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-7.x-646CFF?logo=vite&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9+-3178C6?logo=typescript&logoColor=white)
![Element Plus](https://img.shields.io/badge/Element_Plus-2.11+-409EFF)
![Pinia](https://img.shields.io/badge/Pinia-3.x-F7D336)
![Vue Router](https://img.shields.io/badge/Vue_Router-5.x-4FC08D)
![Axios](https://img.shields.io/badge/Axios-1.15+-5A29E4)

</div>

---

## 📖 简介

**Aura Admin** 是 `AI-Web` Monorepo 下的 Vue3 管理后台应用，使用 Vite、TypeScript、Element Plus、Pinia、Vue Router 与 Axios 构建。当前后台已接入 `core-service` 用户接口，提供登录、注册、路由守卫、用户信息读取、资料更新和账户注销等基础能力。

---

## ✨ 功能介绍

### 🔐 登录与注册
- `/login` 提供用户名密码登录
- `/register` 提供用户名、密码、年龄、性别、邮箱注册
- 登录成功后将 token 写入 Pinia 与 `localStorage`
- 已登录用户访问 `/login` 会自动跳回首页

### 🧭 后台布局
- `/` 使用 `Layout.vue` 作为后台框架
- 左侧菜单包含首页与个人中心
- 顶部栏提供工作台入口和退出登录按钮
- 受保护路由通过 `meta.requiresAuth` + 路由守卫控制

### 👤 用户资料
- `/user/userInfo` 展示账号资料与表单
- 调用 `/user/userInfo` 获取当前登录用户
- 调用 `/user/updateInfo` 更新用户资料
- 调用 `/user/deleteuser/{username}` 注销账户
- 用户资料会与本地缓存合并，便于前端保留编辑状态

### 🌐 请求与状态
- `utils/requests.ts` 统一配置 Axios `baseURL`
- 请求拦截器自动附加 `Authorization: Bearer <token>`
- 响应拦截器统一处理成功提示、错误提示和 401 跳转
- `store/modules/user.ts` 负责 token、用户信息和本地持久化

---

## 🏗️ 技术架构

```
┌──────────────────────────────┐
│          main.ts              │
│ createApp / Router / Pinia    │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│        Vue Router             │
│ public routes / auth guard    │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│          Pages                │
│ Login / Register / Layout     │
│ Home / UserInfo               │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│       API + Axios Layer       │
│ token header / response guard │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│       Spring Boot Core        │
│ /user/register / Login / info │
└──────────────────────────────┘
```

---

## 📁 项目结构

```
apps/admin/
├── src/
│   ├── main.ts                    # 应用入口
│   ├── api/user.ts                # 用户 API
│   ├── pages/
│   │   ├── layout/Layout.vue      # 后台布局
│   │   ├── login/Login.vue        # 登录页
│   │   └── ...
│   ├── store/modules/user.ts      # 用户状态
│   ├── utils/requests.ts          # Axios 封装
│   └── ...
├── vite.config.ts
├── package.json
└── ...
```

---

## 🚀 快速开始

### 环境要求
- Node.js 18+
- pnpm 10+
- Core Service 默认运行在 `http://localhost:8080`

### 安装依赖

```bash
cd AI-Web
pnpm install
```

### 运行

```bash
pnpm dev:admin
```

或直接过滤当前包：

```bash
pnpm --filter @ai-web/admin dev
```

应用默认由 Vite 启动，开发服务器会自动打开浏览器。

### 构建与预览

```bash
pnpm --filter @ai-web/admin build
pnpm --filter @ai-web/admin preview
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] Vue3 + Vite + TypeScript 应用搭建
- [x] Element Plus 自动导入与组件解析
- [x] 登录、注册、首页、布局、个人中心页面
- [x] Pinia token 与用户信息状态
- [x] Axios 请求封装、Bearer Token 和 401 跳转
- [x] 空模板目录清理

### 🔨 进行中
- [ ] 用户管理列表与权限角色
- [ ] 会话列表、消息详情和 AI 配置管理
- [ ] 数据看板与运营统计
- [ ] 后台 API baseURL 环境变量化
- [ ] 页面级表单校验和接口错误细化
