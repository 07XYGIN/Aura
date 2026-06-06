# Aura Web

Aura Web 是 Aura 项目的 Next.js Web 工作台，面向桌面端 AI 聊天、记忆查看、设置和认证流程。

## 技术栈

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS 4
- Radix UI
- lucide-react
- sonner
- next-themes

## 当前功能

- AI 聊天工作台 UI
- 本地消息列表、附件选择和语音输入
- 登录/注册页面
- 记忆页占位布局
- 设置页和主题切换
- 路由切换动画
- fetch 请求封装

## 项目结构

```text
apps/web/
  app/                 # Next.js App Router 页面
  components/
    arua/              # Aura 业务组件
    ui/                # 通用 UI 组件
    ...
  lib/                 # request / utils
  types/               # API、认证和 UI 类型
  package.json
```

## 环境变量

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8080
```

后续如果统一走 BFF，可以把该地址切换为 BFF 服务地址。

## 运行

```bash
cd AI-Web
pnpm install
pnpm dev:web
```

也可以直接过滤当前包：

```bash
pnpm --filter @ai-web/web dev
```

默认运行在 `http://localhost:3000`。

## 构建

```bash
pnpm --filter @ai-web/web build
```

## Roadmap

- [ ] 接入真实登录/注册接口和 token 存储
- [ ] 接入 AI Service 的 SSE 流式对话
- [ ] 接入长期记忆列表和用户资料接口
- [ ] 统一 API 路由规划
- [ ] 补充页面级测试和核心交互测试
