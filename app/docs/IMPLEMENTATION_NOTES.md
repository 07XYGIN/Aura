# Aura Flutter UI Implementation Notes

## 状态管理

本项目统一使用 `Provider`，核心状态集中在 `lib/features/app/application/aura_app_state.dart`。

选择原因：

- 对 Flutter 新手更直观：`ChangeNotifier` 可以类比 Vue/Nest 项目里常见的 store/service。
- 当前阶段主要是页面状态、Tab 切换和 mock 数据，不需要 Riverpod 的额外抽象。
- 后续接入真实 API 时，可以继续把请求结果写入同一个状态层，不需要改页面结构。

## 页面结构

- `features/auth/presentation/auth_screen.dart`：登录/注册页，参考 PC 端登录表单，已删除第三方登录入口。
- `features/chat/presentation/chat_screen.dart`：对话页，包含消息气泡、记忆引用卡片、输入框、思考态。
- `features/memories/presentation/memories_screen.dart`：长期记忆页，包含长期/中期/全部筛选和 mock 记忆卡片。
- `features/settings/presentation/settings_screen.dart`：设置页，包含资料、语言、外观和安全与账号；账号区只保留注销账号。

## 主题

主题 token 来自 PC 端 `AI-Web/apps/web/app/globals.css` 中的 `--aura-*` 变量。

Flutter 侧用 `ThemeExtension<AuraTokens>` 保存 light/dark 两套颜色，页面通过 `context.aura` 获取当前主题色。

## 暂未接入

- 真实登录、注册、聊天 SSE、记忆查询等后端 API。
- 附件上传、语音输入、记忆搜索和账号注销的真实后端流程。
- 高德地图定位相关能力。
