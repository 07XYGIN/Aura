# 💖 Aura Mobile App

<div align="center">

*Aura Mobile App 是 Aura 的 Flutter 移动端客户端工程，面向 Android 交付并保留 Web 调试入口。*
*它会复用 BFF 聚合层的统一 API，让移动端接入同一套认证、聊天、记忆和 Aura 业务能力。*

---

### 客户端
![Flutter](https://img.shields.io/badge/Flutter-3.44+-02569B?logo=flutter&logoColor=white)
![Dart](https://img.shields.io/badge/Dart-3.12+-0175C2?logo=dart&logoColor=white)
![Android](https://img.shields.io/badge/Android-Gradle-3DDC84?logo=android&logoColor=white)
![Material Design](https://img.shields.io/badge/Material-Design-757575?logo=materialdesign&logoColor=white)

</div>

---

## 📖 简介

**Aura Mobile App** 位于仓库根目录 `app/`，是 Aura 的移动端客户端工程。该工程独立于 `AI-Web` pnpm monorepo，使用 Flutter 构建，当前以 Android 端为主要交付目标，并保留 Web 运行入口用于本地界面联调。

移动端后续通过 `AI-Web/apps/bff` 消费统一 API，不直接依赖 Java Core Service 或 Python AI Service 的内部地址。

---

## ✨ 功能介绍

### 📱 移动端工程
- 使用 Flutter 与 Dart 构建跨端客户端
- Android 原生工程已生成，可直接接入模拟器或真机调试
- Web 平台保留为快速 UI 联调入口
- 当前保留 Flutter 默认模板屏幕，后续替换为 Aura 移动端首页

### 🔗 服务依赖
- `AI-Web/apps/bff` 提供统一 API、认证代理和 SSE 转发
- `Server/core-service` 提供用户认证、资料和 Aura 核心业务能力
- `Server/ai-service` 提供 AI 对话、流式响应、记忆和工具调用
- `AI-Web/apps/web`、`AI-Web/apps/PC`、`AI-Web/apps/admin` 继续承载 Web、PC 与管理端

### 🧰 本地配置
- 本地 Flutter SDK 安装位置为 `E:\DevTools\flutter`
- 支持 Flutter 中国镜像加速依赖下载
- Android 构建使用国内 Gradle 与 Maven 镜像
- 相关配置位于 `android/gradle/wrapper/gradle-wrapper.properties`、`android/settings.gradle.kts` 与 `android/build.gradle.kts`

---

## 🏗️ 技术架构

```text
┌────────────────────────────────────────────────────────┐
│                  Flutter Mobile App                    │
│          Material UI · Android · Flutter Web            │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼─────────────────────────────┐
│                    NestJS BFF 层                         │
│             统一 API · token 代理 · SSE 转发              │
└───────────────┬───────────────────────────┬────────────┘
                │                           │
┌───────────────▼──────────────┐ ┌──────────▼─────────────┐
│        Spring Boot Core       │ │      FastAPI AI Service │
│  用户认证 / 用户资料 / Aura    │ │  对话 / 记忆 / 工具 / SSE│
└──────────────────────────────┘ └────────────────────────┘
```

---

## 📁 仓库结构

```text
app/
├── lib/
│   └── main.dart                    # Flutter 应用入口
├── android/
│   ├── app/                         # Android 应用工程
│   ├── build.gradle.kts             # Android 构建配置
│   ├── settings.gradle.kts          # Gradle 插件与仓库配置
│   └── gradle/wrapper/              # Gradle Wrapper
├── web/
│   ├── index.html                   # Flutter Web 调试入口
│   ├── manifest.json
│   └── icons/                       # Web 图标资源
├── pubspec.yaml                     # Flutter 依赖与资源配置
└── analysis_options.yaml            # Dart / Flutter lint 配置
```

---

## 🚀 快速开始

### 环境要求
- Flutter 3.44+
- Dart 3.12+
- Android SDK 与可用模拟器
- Chrome，用于 Flutter Web 调试

### 配置 Flutter 镜像
Windows PowerShell：

```powershell
$env:PUB_HOSTED_URL = 'https://pub.flutter-io.cn'
$env:FLUTTER_STORAGE_BASE_URL = 'https://storage.flutter-io.cn'
```

### 启动移动端
Android 模拟器：

```powershell
cd E:\XYGin\AIfrd\app
flutter emulators --launch Pixel_8_API_36
flutter run
```

Flutter Web：

```powershell
cd E:\XYGin\AIfrd\app
flutter run -d chrome
```

### 检查与构建
```powershell
flutter doctor
flutter analyze
flutter build apk --debug
flutter build web
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] Flutter 工程初始化
- [x] Android 原生工程与 Gradle 配置生成
- [x] Web 调试入口保留
- [x] Material Design 默认模板可运行
- [x] 本地 Flutter 镜像与 Android 构建镜像配置

### 🔜 规划中
- [ ] 替换当前初始界面为 Aura 移动端首页
- [ ] 接入登录、注册与 token 存储
- [ ] 接入 BFF 对话接口和 SSE 流式响应
- [ ] 接入历史会话与长期记忆列表
- [ ] 完成本地主题、请求封装与缓存能力
