# 💖 Aura Core Service

<div align="center">

*Aura Core Service 是 Aura 的 Spring Boot 核心业务服务，负责认证、用户资料、关系数据和业务元数据。*
*它位于 BFF 与 PostgreSQL / Redis 之间，为 Web、PC、Admin 和移动端提供稳定的后端能力。*

---

### 服务端
![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.3.x-6DB33F?logo=springboot&logoColor=white)
![Java](https://img.shields.io/badge/Java-17-007396?logo=openjdk&logoColor=white)
![Maven](https://img.shields.io/badge/Maven-Wrapper-C71A36?logo=apachemaven&logoColor=white)
![MyBatis](https://img.shields.io/badge/MyBatis-3.x-000000)

### 数据库
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Cache-FF4438?logo=redis&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-Auth-000000?logo=jsonwebtokens&logoColor=white)

</div>

---

## 📖 简介

**Aura Core Service** 位于 `Server/core-service/`，是 Aura 的 Java 核心业务服务。它提供用户注册、登录、资料管理、JWT 签发、Redis 登录态缓存，以及 Aura 业务数据的基础读写能力。

客户端侧不直接依赖 Core Service 内部地址，Web、PC、Admin 与根目录 `app/` Flutter 移动端优先通过 `AI-Web/apps/bff` 统一访问。

---

## ✨ 功能介绍

### 🔐 用户认证
- 支持用户注册、登录、退出登录和账号删除
- 登录成功后签发 JWT，并将 `token:{userId}` 写入 Redis
- 支持当前用户资料查询与更新
- 通过 `AuthInterceptor` 校验请求头中的 `Authorization: Bearer <token>`

### 🧬 Aura 业务数据
- 提供 Aura 初始设置、用户画像、关系状态、关系事件等业务接口
- 支持会话、消息、情绪快照、长期记忆等数据写入与查询
- 提供管理端分页查询入口，用于用户画像、人格配置、关系、消息、情绪和记忆资源管理
- 通过 `schema-aura.sql` 与 `schema-invitation.sql` 维护本地数据库结构

### 🧱 服务治理
- 使用统一 `Response<T>` 响应结构
- 通过 `GlobalExceptionHandler` 统一处理异常响应
- 使用 Jakarta Validation 做参数校验
- 使用 MyBatis Mapper 与 XML SQL 管理 PostgreSQL 访问

### 🔌 API 入口
服务默认上下文路径为 `/api`。

| 方法 | 端点 | 鉴权 | 功能 |
| --- | --- | --- | --- |
| POST | `/user/register` | 否 | 用户注册 |
| POST | `/user/login` | 否 | 用户登录，返回 JWT |
| GET | `/user/logout/{userId}` | 是 | 退出登录并删除 Redis token |
| GET | `/user/userInfo` | 是 | 获取当前用户资料 |
| PUT | `/user/updateInfo` | 是 | 更新用户资料 |
| DELETE | `/user/{username}` | 是 | 删除用户账号 |
| GET / POST | `/aura/initial-setting` | 是 | 获取或保存 Aura 初始设置 |
| GET / PUT | `/aura/relationship/status` | 是 | 获取或更新关系状态 |
| GET / POST | `/aura/sessions` | 是 | 查询或创建会话 |
| GET / POST | `/aura/memories` | 是 | 查询或新增记忆 |

---

## 🏗️ 技术架构

```text
┌────────────────────────────────────────────────────────┐
│              Web / PC / Admin / Mobile                 │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼─────────────────────────────┐
│                    NestJS BFF 层                         │
│             鉴权转发 · 响应裁剪 · 统一 API 入口            │
└──────────────────────────┬─────────────────────────────┘
                           │ /api/user/*  /api/aura/*
┌──────────────────────────▼─────────────────────────────┐
│                 Spring Boot Core Service                │
│        UserController · AuraController · AuthInterceptor │
└───────────────┬───────────────────────────┬────────────┘
                │                           │
┌───────────────▼──────────────┐ ┌──────────▼─────────────┐
│          PostgreSQL           │ │          Redis          │
│   用户 / Aura 业务数据 / SQL   │ │    token:{userId} 缓存   │
└──────────────────────────────┘ └────────────────────────┘
```

---

## 📁 仓库结构

```text
core-service/
├── pom.xml                         # Maven 工程配置
├── mvnw / mvnw.cmd                 # Maven Wrapper
└── src/
    ├── main/
    │   ├── java/com/aura/core/
    │   │   ├── controller/         # 用户与 Aura 业务控制器
    │   │   ├── service/            # 登录和 Aura 业务服务
    │   │   ├── mapper/             # MyBatis Mapper 接口
    │   │   ├── entity/             # 数据库实体
    │   │   ├── dto/                # 请求与响应 DTO
    │   │   ├── interceptor/        # 鉴权拦截器
    │   │   ├── common/             # 统一响应与异常处理
    │   │   └── util/               # JWT、Redis、密码工具
    │   └── resources/
    │       ├── application.yml     # 本地配置与环境变量默认值
    │       ├── mapper/             # MyBatis XML SQL
    │       ├── schema-aura.sql     # Aura 业务表结构
    │       └── schema-invitation.sql
    └── test/                       # Spring Boot 测试
```

---

## 🚀 快速开始

### 环境要求
- Java 17+
- Maven Wrapper（仓库已提供 `mvnw` / `mvnw.cmd`）
- PostgreSQL 16+
- Redis 7+

### 配置环境变量
`src/main/resources/application.yml` 已提供本地默认值，也支持环境变量覆盖。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_HOST` | `localhost` | PostgreSQL 主机 |
| `DB_PORT` | `5432` | PostgreSQL 端口 |
| `DB_NAME` | `Aura` | 数据库名 |
| `DB_SCHEMA` | `public` | Schema |
| `DB_USERNAME` | `postgres` | 数据库用户 |
| `DB_PASSWORD` | `123456` | 数据库密码 |
| `REDIS_HOST` | `localhost` | Redis 主机 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `REDIS_DATABASE` | `0` | Redis DB |
| `REDIS_PASSWORD` | 空 | Redis 密码 |
| `JWT_SECRET_KEY` | `change-me-to-a-strong-32-byte-secret-key` | JWT 密钥 |
| `JWT_EXPIRE_TIME` | `86400000` | JWT 过期时间，单位毫秒 |
| `INVITE_REGISTRATION_REQUIRED` | `true` | 是否要求邀请码注册 |

### 启动核心后端服务
Windows PowerShell：
```powershell
cd Server/core-service
.\mvnw.cmd spring-boot:run
```

Linux / macOS：
```bash
cd Server/core-service
./mvnw spring-boot:run
```

服务默认运行在：

```text
http://localhost:8080/api
```

### 测试与构建
```bash
./mvnw test
./mvnw clean package
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] Spring Boot 工程与 Maven Wrapper 搭建
- [x] 用户注册、登录、退出登录、资料查询和资料更新
- [x] JWT 签发、解析与 Redis token 缓存
- [x] 统一响应结构、异常处理、参数校验与鉴权拦截器
- [x] Aura 用户画像、会话、消息、关系、情绪、记忆等实体与 DTO
- [x] Aura 业务接口与管理端分页查询入口
- [x] PostgreSQL schema 脚本与 MyBatis Mapper 配置

### 🔜 规划中
- [ ] 补充 Core Service 关键接口集成测试
- [ ] 扩展管理端写操作审计与权限分层
- [ ] 完善邀请码与用户数据导出流程

---

## ⚠️ 弃用说明

`Server/core-service` 已弃用，不再作为 Aura 当前认证或业务服务入口维护。

该目录仅用于历史代码追溯；新的后端能力请优先围绕 `Server/ai-service` 开发。
