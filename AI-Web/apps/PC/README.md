# Aura PC

Aura PC 是 Aura 项目的 Vue 3 桌面客户端，承担聊天、记忆、设置和登录注册等核心使用场景。

## 技术栈

- Vue 3 + Vite
- TypeScript
- Pinia
- Vue Router
- Tailwind CSS
- reka-ui / shadcn-vue 风格组件
- Axios
- Server-Sent Events

## 当前功能

- 登录和注册页面
- 左侧导航与主布局
- 聊天页面和 SSE 客户端封装
- 历史消息读取
- 记忆列表页面
- 设置页面
- 主题切换入口

## 项目结构

```text
apps/PC/
  src/
    api/               # 登录、消息、用户接口
    components/
      pages/           # 页面级组件
      ui/              # 通用 UI 组件
      ...
    pages/             # 路由页面
    router/            # Vue Router
    store/             # Pinia
    utils/             # request / SSE
    ...
  vite.config.ts
  package.json
```

## 运行

```bash
cd AI-Web
pnpm install
pnpm --filter @ai-web/pc dev
```

## 构建

```bash
pnpm --filter @ai-web/pc build
```

## Roadmap

- [ ] 打通 AI Service SSE 聊天闭环
- [ ] 接入真实记忆列表和删除接口
- [ ] 统一登录态和错误提示
- [ ] 优化聊天消息渲染和 Markdown 展示
- [ ] 补充基础页面测试
