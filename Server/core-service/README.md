# Core Service - 核心认证服务

Spring Boot 3.3.5 构建的轻量级用户认证与管理微服务，提供 JWT 令牌认证、Redis 会话缓存和 PostgreSQL 数据持久化。

## 技术栈

### 框架与核心
- **Spring Boot** 3.3.5 - 企业级 Java 框架
- **Java** 17 - 编程语言
- **Maven** 3.x - 项目构建工具

### 数据库与 ORM
- **PostgreSQL** - 关系型数据库
- **MyBatis** 3.0.3 - SQL 映射框架

### 认证与安全
- **JWT (JJWT)** 0.12.6 - 令牌认证
- **Spring Security Crypto** - BCrypt 密码加密
- **自定义 AuthInterceptor** - 请求验证拦截器

### 缓存
- **Redis** - 会话/令牌存储

### 工具库
- **Jakarta Validation** - Bean 数据验证
- **Lombok** - 代码生成（Getter/Setter）
- **JetBrains Annotations** - 代码注解

## 已实现功能

### 1. 用户管理
- **注册**：创建新用户账户，支持邮箱验证和密码加密
- **登录**：用户认证并颁发 JWT 令牌
- **登出**：通过从 Redis 删除令牌来使其失效
- **获取用户信息**：查询用户资料（需认证）
- **更新用户信息**：修改邮箱、年龄、性别等
- **删除用户**：删除用户账户

### 2. 认证与授权
- 基于 JWT 的令牌认证（24 小时过期）
- 通过 AuthInterceptor 在所有端点进行令牌验证（除 `/user/Login` 和 `/user/register`）
- Redis 支持的令牌黑名单用于登出功能
- Bearer 令牌方案（Authorization 请求头）

### 3. 数据库模式

**Users 表：**
```
- id (UUID)
- username (唯一标识符)
- password (BCrypt 加密)
- email (邮箱验证)
- sex (性别)
- age (年龄)
```

## API 端点

| 方法 | 端点 | 认证 | 功能 |
|------|------|------|------|
| POST | `/user/register` | 否 | 用户注册 |
| POST | `/user/Login` | 否 | 用户登录 |
| GET | `/user/logout/{userId}` | 是 | 令牌失效 |
| GET | `/user/userInfo` | 是 | 获取用户资料 |
| PUT | `/user/updateInfo` | 是 | 更新用户信息 |
| DELETE | `/user/deleteuser/{username}` | 是 | 删除用户账户 |

## 项目结构

```
core-service/
├── pom.xml                                    # Maven 配置
├── src/main/
│   ├── java/com/example/springboot_test/
│   │   ├── SpringbootTestApplication.java    # 应用入口
│   │   ├── controller/
│   │   │   └── userController.java           # REST API 端点
│   │   ├── service/
│   │   │   └── LoginService.java             # 业务逻辑
│   │   ├── mapper/
│   │   │   └── userMapper.java               # MyBatis 数据访问
│   │   ├── Entity/
│   │   │   └── Users.java                    # 数据库实体
│   │   ├── DTO/
│   │   │   └── UserDto.java                  # 数据传输对象
│   │   ├── util/
│   │   │   ├── Crypto.java                   # 密码加密（BCrypt）
│   │   │   ├── JWTUtil.java                  # JWT 令牌生成/验证
│   │   │   └── RedisUtil.java                # Redis 操作
│   │   ├── interceptor/
│   │   │   └── AuthInterceptor.java          # 请求认证拦截器
│   │   ├── config/
│   │   │   └── WebConfig.java                # Web 配置与 CORS
│   │   └── common/
│   │       └── Response.java                 # 标准化 API 响应
│   └── resources/
│       ├── application.yml                   # 应用配置
│       └── mapper/UserMapper.xml             # MyBatis SQL 映射
└── target/                                   # 构建输出
```

## 配置

**数据库**：PostgreSQL localhost:5432，数据库 `Aura`
**Redis**：localhost:6379，数据库 0
**JWT 过期时间**：24 小时（86400000 毫秒）

## 快速开始

### 前置条件
- Java 17+
- Maven 3.x
- PostgreSQL
- Redis

### 构建

```bash
mvn clean package
```

### 运行

```bash
java -jar target/springboot-test-1.0.jar
```

或使用 Maven：
```bash
mvn spring-boot:run
```

服务运行在 `http://localhost:8080`

## 架构模式

- **Controller 层**：处理 HTTP 请求的 REST 端点
- **Service 层**：业务逻辑（LoginService）
- **数据访问层**：MyBatis 映射器接口与 XML SQL 定义
- **工具层**：JWT、加密、Redis 操作
- **拦截器模式**：请求级别的认证验证
- **DTO 模式**：层间数据传输与验证

## 安全特性

- BCrypt 密码加密存储
- JWT 令牌 24 小时有效期
- Redis 令牌黑名单机制
- 请求拦截器强制认证
- 标准化错误响应处理
