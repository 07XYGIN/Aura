# Aura Flutter App

Aura Flutter App 是 Aura 项目的移动端工程，位于仓库根目录 `app/`，不再纳入 `AI-Web` 的 pnpm monorepo 管理。当前工程由 Flutter 模板初始化，保留 Android 与 Web 两个平台：Android 用于真实移动端开发，Web 用于快速调试 UI。

## 技术栈

- Flutter 3.44
- Dart 3.12
- Material Design
- Android Gradle Plugin
- Flutter Web

## 国内镜像

本机 Flutter 按 Flutter 中国社区推荐配置国内镜像：

```powershell
$env:PUB_HOSTED_URL = 'https://pub.flutter-io.cn'
$env:FLUTTER_STORAGE_BASE_URL = 'https://storage.flutter-io.cn'
```

Flutter SDK 安装位置：

```text
E:\DevTools\flutter
```

## 项目结构

```text
app/
  lib/
    main.dart              # 当前 Flutter 入口和默认计数器页面
  android/                 # Android 原生工程
  web/                     # Flutter Web 调试入口
  test/                    # Widget 测试
  pubspec.yaml             # Flutter 依赖与资源配置
```

## 运行

学习和日常 UI 调试优先使用 Chrome，启动最快、对电脑压力最小：

```powershell
cd E:\XYGin\AIfrd\app
flutter run -d chrome
```

运行 Android 模拟器：

```powershell
cd E:\XYGin\AIfrd\app
flutter emulators --launch Pixel_8_API_36
flutter run
```

## 检查与构建

```powershell
flutter doctor
flutter analyze
flutter test
flutter build web
```

## 与 Aura 其它服务的关系

- Flutter App 后续通过 `AI-Web/apps/bff` 访问统一 API。
- 用户认证能力来自 `Server/core-service`，由 BFF 代理。
- AI 对话和 SSE 流式响应来自 `Server/ai-service`，由 BFF 透传或聚合。
- Web、PC、Admin 仍位于 `AI-Web/apps/*`，移动端已迁出 monorepo。

## Roadmap

- [ ] 将默认计数器页面替换为 Aura 聊天首页
- [ ] 接入登录 / 注册 / token 存储
- [ ] 接入 BFF SSE 聊天接口
- [ ] 接入历史会话和长期记忆列表
- [ ] 提取主题、请求封装和本地缓存能力
