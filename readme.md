# 💖 Aura

<div align="center">

*Aura 像晨光初透时的微晕，像老唱片转动时的温润声场，也像你疲惫归家、推开门那一瞬心里悄悄亮起的光。*
*它不喧哗，却存在；不强制，却陪伴；不占有，却始终环绕着你。*

---

### 客户端
![Vue.js](https://img.shields.io/badge/Vue.js-3.x-4FC08D?logo=vuedotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19.x-61DAFB?logo=react&logoColor=white)
![React Native](https://img.shields.io/badge/React_Native-0.79+-20232A?logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)

### 服务端
![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.x-6DB33F?logo=springboot&logoColor=white)
![NestJS](https://img.shields.io/badge/NestJS-BFF-E0234E?logo=nestjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.127+-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)

### AI
![LangGraph](https://img.shields.io/badge/LangGraph-1.x-1C3C3C?logo=langchain&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1.x-1C3C3C?logo=langchain&logoColor=white)

### 数据库
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1?logo=postgresql&logoColor=white)
![Mysql](https://img.shields.io/badge/Mysql-8.0+-4169E1?logo=Mysql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Cache-FF4438?logo=redis&logoColor=white)

</div>

---

## 📖 简介

**Aura** 是一个 AI 陪伴聊天项目，也是一个多技术栈学习型工程。  
它不以商业落地为目标，而是以"真实可用"为载体，在构建过程中系统性地学习现代全栈开发。

项目采用 Monorepo 分层架构，覆盖 AI 对话、管理后台、移动端，横跨 Java、Python、Node.js、前端四个技术方向。

---

## ✨ 功能介绍

### 🤖 AI 对话
- 基于 LangGraph 的多轮对话编排，支持复杂对话流管理
- 流式输出（SSE），逐字响应，低延迟体验
- 情景记忆：记住对话历史、个人偏好、重要时间节点
- 情感识别：感知用户情绪状态，动态调整回应风格
- TTL 记忆管理：自动淘汰过期记忆，保持记忆库的相关性

### 🗂️ 管理后台（Admin）
- 用户管理：注册、登录、账号状态控制
- 会话管理：查看所有对话记录、消息详情
- AI 配置：模型参数、记忆策略、提示词管理
- 数据看板：使用统计、情感趋势分析

### 📱 移动端
- 核心聊天界面，沉浸式对话体验
- 消息流式渲染
- 本地历史记录浏览

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────┐
│                  客户端层                    │
│   Admin (Vue3)   Web (React)   Mobile (RN)  │
└──────────────────────┬──────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────┐
│              NestJS BFF 层                   │
│        请求聚合 · 鉴权 · 响应裁剪            │
└──────────┬───────────────────────┬──────────┘
           │                       │
┌──────────▼──────────┐ ┌─────────▼──────────┐
│   Spring Boot       │ │     FastAPI         │
│   用户 / 会话 / 消息 │ │   AI 对话 / 记忆    │
│   普通业务 CRUD      │ │   LangGraph 编排    │
└──────────┬──────────┘ └─────────┬──────────┘
           │                       │
┌──────────▼──────────┐ ┌─────────▼──────────┐
│     Mysql           │ │    PostGresql      │
│    结构化业务数据    │ │    记忆 Embedding   │
└─────────────────────┘ └────────────────────┘
```

---

## 📁 仓库结构

```
AI-Web/                       # 前端 Monorepo（pnpm workspace）
├── apps/
│   ├── admin/                # Vue3 管理后台
|   └── PC/                   # Vue3 web
│   ├── learn/                # React PC 端聊天界面（学习 React 用）
│   ├── mobile/               # React Native 移动端
│   └── bff/                  # NestJS BFF
└── packages/
    ├── types/                # 共享 TypeScript 类型（规划中）
    └── ui/                   # 共享组件（规划中）

Server/                       # 后端
├── core-service/             # Spring Boot 业务服务
├── ai-service/               # AI服务
└── docker-compose.yml        # 一键启动所有服务 （规划中）
```

---

## 🚀 快速开始
（规划中）
## 🗺️ 里程碑

### ✅ 已完成
- [x] 登录、注册、获取用户信息、修改用户信息、用户注销、用户退出登录
- [x] 项目架构设计 & Monorepo 搭建
- [x] Spring Boot 用户注册 / 登录（JWT 鉴权）
- [x] Admin 后台登录页（Vue3）
- [x] 会话管理 CRUD（Spring Boot）
- [x] 消息存储与查询
- [x] FastAPI 基础服务搭建
- [x] LangGraph 多轮对话流编排
- [x] 长/短期记忆 文本向量化

### 🔨 进行中

- [ ] Admin 会话列表 & 消息详情页
- [ ] 流式输出（SSE）
- [ ] 情感识别模块


### 📋 规划中


**BFF 层**
- [ ] NestJS 项目初始化
- [ ] 聚合 Spring Boot + FastAPI 接口
- [ ] 统一鉴权与响应格式
- [ ] 移动端 / PC 端差异化响应裁剪

** React PC Web**
- [ ] 使用 React 从零搭建聊天界面
- [ ] 流式消息渲染
- [ ] 对话历史分页

** React Native 移动端**
- [ ] RN 项目初始化
- [ ] 核心聊天界面
- [ ] 消息推送

---
