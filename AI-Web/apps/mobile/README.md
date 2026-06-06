# 💖 Aura Mobile

<div align="center">

*Aura 的 React Native 移动端骨架，面向后续 Android / iOS 陪伴式聊天体验。*

---

![React Native](https://img.shields.io/badge/React_Native-0.85.3-20232A?logo=react&logoColor=61DAFB)
![React](https://img.shields.io/badge/React-19.2.3-61DAFB?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.8+-3178C6?logo=typescript&logoColor=white)
![Android](https://img.shields.io/badge/Android-ready-3DDC84?logo=android&logoColor=white)
![iOS](https://img.shields.io/badge/iOS-ready-000000?logo=apple&logoColor=white)

</div>

---

## 📖 简介

**Aura Mobile** 是 `AI-Web` Monorepo 下的 React Native CLI 移动端应用。当前已经删除 React Native 默认模板屏幕、模板测试和 `@react-native/new-app-screen` 依赖，只保留可启动的基础骨架：`index.js` 入口、`App.tsx` 空容器、Android / iOS 原生工程与 Metro 配置。

---

## ✨ 功能介绍

### 📱 当前骨架
- React Native 0.85.3 工程保留
- Android Gradle 工程与 iOS Xcode 工程保留
- `SafeAreaProvider` 与 `StatusBar` 保留在入口中
- `App.tsx` 只渲染一个全屏空容器，等待后续业务页面接入

### 🧹 已清理模板
- 删除 `@react-native/new-app-screen`
- 删除 `__tests__/App.test.tsx`
- 删除 `jest.config.js`
- 删除默认模板屏幕文案和示例渲染

### 🔮 业务规划
- 聊天首页：接入 AI Service SSE 或 BFF 代理后的流式对话
- 登录注册：复用核心服务用户体系
- 记忆与设置：移动端查看长期记忆、配置偏好和账户状态
- 本地缓存：保存登录态、最近会话和用户偏好

---

## 🏗️ 技术架构

```
┌──────────────────────────────┐
│           index.js            │
│      AppRegistry register     │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│           App.tsx             │
│ SafeAreaProvider / StatusBar  │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│     Empty React Native View   │
│      等待业务页面接入          │
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────┐
│ Android / iOS Native Runtime  │
└──────────────────────────────┘
```

---

## 📁 项目结构

```
apps/mobile/
├── App.tsx                         # React Native 空应用骨架
├── index.js                        # AppRegistry 注册入口
├── package.json                    # 脚本与依赖
├── metro.config.js                 # Metro 配置
├── android/                        # Android 原生工程
├── ios/                            # iOS 原生工程与 Podfile
└── ...
```

---

## 🚀 快速开始

### 环境要求
- Node.js 22.11+（当前 `package.json` engines 要求）
- pnpm 10+
- Android Studio + Android SDK（运行 Android）
- Xcode + CocoaPods（运行 iOS，仅 macOS）

请先完成 React Native 官方本地开发环境配置。

### 安装依赖

```bash
cd AI-Web
pnpm install
```

### 启动 Metro

```bash
pnpm --filter mobile start
```

### 运行 Android

```bash
pnpm --filter mobile android
```

### 运行 iOS

首次安装或原生依赖变更后：

```bash
cd AI-Web/apps/mobile/ios
bundle install
bundle exec pod install
```

启动应用：

```bash
cd AI-Web
pnpm --filter mobile ios
```

### 检查

```bash
pnpm --filter mobile lint
```

---

## 🗺️ 里程碑

### ✅ 已完成
- [x] React Native 0.85.3 工程初始化
- [x] Android / iOS 原生工程生成
- [x] 默认模板屏幕与测试模板删除
- [x] `App.tsx` 收敛为可启动空骨架
- [x] Monorepo workspace 包接入

### 🔨 进行中
- [ ] 搭建移动端聊天页面与输入区
- [ ] 接入登录注册和 token 存储
- [ ] 接入 AI 对话流、历史记录和记忆数据
- [ ] 增加移动端导航、主题和本地缓存
