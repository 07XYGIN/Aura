# Aura Admin

## 在整体架构中的位置

- `apps/admin` 是 Vue 3 管理后台。
- `apps/bff` 后续承接管理端聚合 API。
- 移动端已迁移为仓库根目录 `app/` 下的 Flutter 工程，不再属于 `AI-Web` pnpm workspace。

Aura Admin 是 Aura 项目的 Vue 3 管理后台，负责用户资料、后台工作台和后续运营管理能力的承载。

## 技术栈

- Vue 3 + Vite
- TypeScript
- Element Plus
- Pinia
- Vue Router
- Axios

## 当前功能

- 登录与注册页面
- 后台基础布局
- 路由守卫与登录态判断
- 用户信息读取、编辑和注销入口
- Axios 请求封装与 token 注入
- Pinia 用户状态持久化

## 项目结构

```text
apps/admin/
  src/
    api/              # 用户 API
    pages/            # 登录、注册、布局、用户页
    router/           # 路由配置
    store/            # Pinia 状态
    utils/            # Axios 封装
    ...
  vite.config.ts
  package.json
```

## 运行

```bash
cd AI-Web
pnpm install
pnpm dev:admin
```

也可以直接过滤当前包：

```bash
pnpm --filter @ai-web/admin dev
```

## 构建

```bash
pnpm --filter @ai-web/admin build
```

## Roadmap

- [ ] 用户管理列表
- [ ] 会话列表和消息详情
- [ ] AI 配置管理
- [ ] 数据看板
- [ ] 环境变量化 API baseURL
- [ ] 更完整的表单校验和错误提示
