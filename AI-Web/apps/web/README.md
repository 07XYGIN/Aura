# Aura Web

Aura Web 是 Aura 项目的 Next.js 用户端，面向 AI 陪伴、聊天、记忆、设置和认证流程。

## 技术栈

- Next.js 16
- React 19
- TypeScript
- Zustand
- Tailwind CSS 4
- shadcn/ui、Radix UI
- lucide-react
- sonner
- next-themes

## 当前能力

- AI 聊天工作台 UI
- 通过 BFF `/api/chat/sse` 接入 AI 流式对话
- SSE 文本分片增量渲染
- 情感状态 metadata 展示
- 登录 / 注册页面
- Zustand 登录态存储
- 记忆页与设置页基础布局
- 附件选择与语音输入
- 主题切换与路由过渡动画

## 环境变量

```dotenv
NEXT_PUBLIC_BFF_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:3000
```

聊天页优先读取 `NEXT_PUBLIC_BFF_URL`，缺省时使用 `NEXT_PUBLIC_API_URL`，最终请求：

```text
POST /api/chat/sse
```

## 运行

```bash
cd AI-Web
pnpm install
pnpm dev:web
```

或：

```bash
pnpm --filter @ai-web/web dev
```

默认运行在 `http://localhost:3000`。如果 BFF 也使用 3000 端口，请为其中一个服务指定其他端口。

## 构建

```bash
pnpm --filter @ai-web/web build
```

## Roadmap

- [x] 接入真实登录 / 注册接口和 token 存储
- [x] 接入 BFF SSE 流式对话
- [x] 展示 AI 情感状态 metadata
- [ ] 抽离 `useChatStream`、`useAutoScroll`、`useVoiceInput`
- [ ] 接入长期记忆列表和用户资料接口
- [ ] 补充核心交互测试
