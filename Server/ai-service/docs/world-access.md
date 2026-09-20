# World Access v1

主聊天的工具新增 `search_web` 和 `fetch_url`：

`Agent Tool → WorldService → WorldProvider → MCPWorldProvider → 本地 stdio MCP`

不新增数据库表或迁移；没有后台联网、主动新闻、Maps、浏览器自动化或 MCP Hub。
`CHAT_TOOLS` 静态注册五个工具，保留现有 LangGraph/SSE 流程。

## 启用

在 `Server/ai-service` 执行 `uv sync`，在本地 `.env` 配置后重启后端：

```dotenv
WORLD_ENABLED=true
BRAVE_SEARCH_API_KEY=填写你自己的搜索API密钥
WORLD_MCP_COMMAND=
WORLD_MCP_ARGS=
```

Brave Search Key 在 [Brave API 控制台](https://api-dashboard.search.brave.com/documentation/guides/authentication)
创建，搜索使用 [Web Search API](https://api-dashboard.search.brave.com/api-reference/web/search/get)。
是否收费及额度以你的订阅为准。不要提交本地 `.env`。
网页阅读无需 Brave Key；缺少 Key 时仅搜索返回 `not_configured`。默认不开启联网。

本版选用 MCP SDK 1.x（依赖限定 `<2`），只支持 **stdio**，没有开放 HTTP MCP 端口。
每次调用启动一个子进程，结束或超时后关闭 session/进程，无长期驻留或启动时外部探测。
MCP server 不加载 `.env`；父进程只向其传递 Brave Key 和 UTF-8 配置，SDK 另外继承启动进程所需的基础系统环境，不传模型、JWT 或数据库密钥。

命令参数留空即可使用当前虚拟环境的 Python 启动内置模块。
高级配置 `WORLD_MCP_COMMAND` 必须配合 JSON 数组 `WORLD_MCP_ARGS`，不是 shell 命令字符串。
自定义命令是管理员信任的本地可执行代码，必须实现同名工具、内部数据 Contract 和同等网络访问限制。
不要复制未知 MCP 命令；客户端预检**无法保证任意第三方服务的重定向或 DNS 安全**。
后续 HTTP transport 或其他供应商应在 Provider 层独立接入，不能在 Agent Tool 中引入 SDK。

## 行为与限制

- 实时/明确搜索请求 → `search_web`；直接提供 URL 要求阅读 → `fetch_url`；普通稳定知识和记忆查询不自动搜索。
- 每轮最多一次搜索、三页正文；搜索后把需要的页面合并到第二批调用。两轮 World 工具后主模型不再绑定工具，直接回答，避免无限循环。这是调用预算，不是能力动态路由。
- 输出使用 Pydantic Contract，工具返回 camelCase 字段；`searchedAt` / `fetchedAt` 为查询时间，不是文章发布日期。无法确定发布时间时 `publishedAt=null`。
- 搜索最多五条、每条摘要 1200 字符；正文最多 12000 字符，超长 `truncated=true`。
- 仅 HTML/纯文本，不执行 JS，不读 PDF/二进制或登录页面，不绕过站点限制。读取源文件上限 1 MiB；不接受压缩响应，避免解压炸弹。部分动态/压缩站点会失败，应如实告知用户。
- WorldService 超时 20 秒（包含启动、DNS、MCP）；底层连接 5 秒、读 10 秒，SDK 清理子进程可能有少量额外开销。失败以 `ok=false` 返回，不向聊天泄漏 provider 原始异常。
- SSRF：仅 HTTP(S) 80/443、禁止凭据、控制字符、本地域名、私有/保留/链路本地/组播和 IPv6 隧道地址。拒绝任何包含非公开 IP 的 DNS 结果；内置阅读器连接已验证 IP，保留原始 TLS SNI/证书校验；最多三次跳转且每跳重新检查。不使用环境代理，不转发 Cookie 或 Authorization。
- 标题、摘要、来源和正文都标记为不可信数据，网页不能改变 system/user/tool 权限。为硬性保护记忆，包含 Web 调用的当前回合禁止 `save_memory_tool` 写入，包含同批工具调用也拦截；用户可下一轮单独确认保存。这不改动 Memory Engine。
- `logging_utils.py` 记录工具名、输入指纹/长度、URL host、耗时、成功状态、结果数和错误码；不记录原始搜索词、URL query/path、网页正文或秘密。保留输入指纹便于关联故障，同时避免私密查询和带 token 的 URL 进入日志。
- Prompt Injection 没有通用“清洗后完全可信”的保证；保留原文作为数据，依靠系统约束、只读工具和记忆写入边界，不声称删除关键词即可消除风险。

## 验证

```powershell
uv run python -m unittest discover -s tests
# 可选：实际模型的 8 个选工具场景与 1 个恶意网页场景；会消耗模型额度
$env:AURA_RUN_LIVE_WORLD_TESTS="1"
uv run python -m unittest discover -s tests -p test_world_selection_live.py
```

默认测试覆盖 Provider 成功/空结果/超时/异常/截断、非法 URL/DNS/跳转、TLS 固定 IP、子进程 secret 隔离、真实 stdio 握手、缺 key 降级、工具预算和恶意网页触发记忆写入的阻断。
真实模型测试只检查选工具，不执行搜索，不代表 Brave 端到端检索成功；需要有效 Key 后另做实际搜索验收。
