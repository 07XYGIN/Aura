# Aura Core Service

## 在整体架构中的位置

- Core Service 提供用户注册、登录、资料和 token 状态能力。
- Web、PC、Admin 与根目录 `app/` Flutter 移动端都应优先通过 `AI-Web/apps/bff` 访问这些能力。
- 客户端不直接持有 Core Service 内部地址，BFF 负责统一代理和响应裁剪。

Aura Core Service 是基于 Spring Boot 的核心业务服务，负责用户注册、登录、资料管理、JWT 签发和 Redis 登录态缓存。

## 技术栈

- Java 17
- Spring Boot 3.3.5
- Maven
- MyBatis
- PostgreSQL
- Redis
- JWT / JJWT
- BCrypt

## 当前能力

- 用户注册
- 用户登录
- JWT 签发
- Redis 写入 `token:{userId}`
- 用户退出登录
- 当前用户资料查询
- 用户资料更新
- 用户删除
- 请求鉴权拦截
- 参数校验和统一响应

## API

服务默认上下文路径：

```text
/api
```

| 方法 | 端点 | 鉴权 | 功能 |
| --- | --- | --- | --- |
| POST | `/user/register` | 否 | 用户注册 |
| POST | `/user/login` | 否 | 用户登录，返回 JWT |
| GET | `/user/logout/{userId}` | 是 | 退出登录并删除 Redis token |
| GET | `/user/userInfo` | 是 | 获取当前用户资料 |
| PUT | `/user/updateInfo` | 是 | 更新用户资料 |
| DELETE | `/user/{username}` | 是 | 删除用户账号 |

## 认证链路

```text
用户登录
  -> Core Service 校验密码
  -> 签发 JWT，sub = userId
  -> 写入 Redis token:{userId}
  -> 前端携带 Authorization: Bearer <token>
  -> BFF / Core Service 校验 JWT 与 Redis token
```

## 环境变量

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
| `JWT_SECRET_KEY` | `change-me-to-a-strong-32-byte-secret-key` | JWT 密钥 |
| `JWT_EXPIRE_TIME` | `86400000` | JWT 过期时间，单位毫秒 |

## 运行

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

## 测试与构建

```bash
./mvnw test
./mvnw clean package
```
