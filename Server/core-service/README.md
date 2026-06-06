# 💖 Aura Core Service

<div align="center">

*Aura 的核心业务服务，负责用户认证、资料管理、JWT 令牌与 Redis 会话缓存。*

---

![Java](https://img.shields.io/badge/Java-17-007396?logo=openjdk&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.3.5-6DB33F?logo=springboot&logoColor=white)
![Maven](https://img.shields.io/badge/Maven-3.x-C71A36?logo=apachemaven&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Aura-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-token_cache-FF4438?logo=redis&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-0.12.6-000000?logo=jsonwebtokens&logoColor=white)

</div>

---

## 📖 简介

**Core Service** 是 Aura 的 Spring Boot 核心认证服务，提供用户注册、登录、登出、资料查询、资料更新和账户删除能力。服务使用 PostgreSQL 持久化用户数据，使用 Redis 缓存登录令牌，并通过自定义拦截器完成 Bearer Token 校验。

---

## ✨ 功能介绍

### 👤 用户管理
- 用户注册：保存用户名、密码、邮箱、性别、年龄等基础资料
- 用户登录：校验密码后签发 JWT，并写入 Redis 缓存
- 用户登出：删除 `token:{userId}` 缓存，使令牌失效
- 用户信息：根据 Authorization Header 解析用户 ID 并返回资料
- 资料更新：支持邮箱、性别、年龄、用户名等字段更新
- 账户删除：按用户名删除用户记录

### 🔐 认证与安全
- BCrypt 密码哈希存储
- JJWT 生成和解析 JWT 令牌
- `AuthInterceptor` 拦截受保护接口
- `/user/Login` 与 `/user/register` 放行，其余接口默认需要鉴权
- Jakarta Validation + `GlobalExceptionHandler` 返回 422 参数错误

### 🔌 API 端点

| 方法 | 端点 | 认证 | 功能 |
|------|------|------|------|
| POST | `/user/register` | 否 | 用户注册 |
| POST | `/user/Login` | 否 | 用户登录，返回 JWT |
| GET | `/user/logout/{userId}` | 是 | 登出并删除 Redis 令牌 |
| GET | `/user/userInfo` | 是 | 获取当前用户资料 |
| PUT | `/user/updateInfo` | 是 | 更新用户资料 |
| DELETE | `/user/deleteuser/{username}` | 是 | 删除用户账户 |

---

## 🏗️ 技术架构

```
┌──────────────────────────────┐
│       Web / Admin / BFF       │
└───────────────┬──────────────┘
                │ HTTP + Bearer Token
┌───────────────▼──────────────┐
│        userController         │
│   注册 / 登录 / 资料 / 注销    │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│        AuthInterceptor        │
│   登录注册放行，其余接口鉴权    │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│          LoginService         │
│   业务编排 / 密码校验 / JWT     │
└───────┬────────────────┬─────┘
        │                │
┌───────▼────────┐ ┌─────▼─────────────┐
│ PostgreSQL      │ │ Redis              │
│ users 表        │ │ token:{userId}     │
└────────────────┘ └───────────────────┘
```

---

## 📁 项目结构

```
core-service/
├── pom.xml
├── mvnw / mvnw.cmd
├── src/main/
│   ├── java/com/example/springboot_test/
│   │   ├── SpringbootTestApplication.java     # 应用入口
│   │   ├── controller/userController.java     # 用户 REST API
│   │   ├── service/LoginService.java          # 用户业务逻辑
│   │   ├── interceptor/AuthInterceptor.java   # 请求鉴权拦截器
│   │   └── ...
│   └── resources/
│       ├── application.yml                    # 本地应用配置
│       └── mapper/UserMpaaer.xml              # MyBatis SQL 映射
└── ...
```

---

## 🚀 快速开始

### 环境要求
- Java 17+
- Maven 3.x，或使用仓库内 `mvnw`
- PostgreSQL，本地数据库名默认为 `Aura`
- Redis，本地端口默认为 `6379`

### 配置

本地配置位于 `src/main/resources/application.yml`：

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/Aura?currentSchema=public
  data:
    redis:
      host: localhost
      port: 6379
jwt:
  expire-time: 86400000
```

生产环境建议将数据库密码和 JWT 密钥迁移到环境变量或安全配置中心。

### 运行

```bash
cd Server/core-service
./mvnw spring-boot:run
```

Windows PowerShell：

```powershell
cd Server/core-service
.\mvnw.cmd spring-boot:run
```

服务默认运行在 `http://localhost:8080`。

### 构建与测试

```bash
./mvnw test
./mvnw clean package
java -jar target/springboot_test-0.0.1-SNAPSHOT.jar
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] Spring Boot 3.3.5 项目搭建
- [x] 用户注册、登录、登出接口
- [x] BCrypt 密码加密与 JWT 令牌生成
- [x] Redis 令牌缓存与失效处理
- [x] 用户资料查询、更新和删除
- [x] MyBatis Mapper 与 PostgreSQL `users` 表访问
- [x] 统一响应结构和参数校验异常处理

### 🔨 进行中
- [ ] 生产环境密钥外置与配置分层
- [ ] 与 NestJS BFF 的统一鉴权链路
- [ ] 会话、消息等业务模块扩展
- [ ] 接口测试与集成测试补齐
