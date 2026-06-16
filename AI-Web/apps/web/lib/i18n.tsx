'use client'

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type Locale = 'zh-CN' | 'en-US'

const STORAGE_KEY = 'aura-locale'

const messages = {
  'zh-CN': {
    'app.companionConsole': '陪伴控制台',
    'app.description': '用于对话、记忆和个人设定的 AI 陪伴工作台。',
    'app.navigate': '导航',
    'nav.chat': 'AI 对话',
    'nav.memories': '记忆',
    'nav.settings': '设置',
    'account.name': '用户账号',
    'account.status': '等待后端同步',
    'account.description': '资料、偏好和伴侣权限会在账号服务同步后显示在这里。',
    'chat.placeholder': '给 Arua 发消息...',
    'chat.uploadImage': '上传图片',
    'chat.startVoice': '开始语音输入',
    'chat.stopVoice': '停止语音输入',
    'chat.send': '发送消息',
    'chat.emotion': '情绪',
    'chat.emotionUpdated': '情绪已更新',
    'chat.accountSyncFailed': '账号同步失败',
    'chat.accountSyncFailedDescription': '请检查 BFF 服务是否正在运行。',
    'chat.streamFailed': '消息流失败',
    'chat.invalidChunk': 'Arua 返回了无法解析的流片段。',
    'chat.tryAgain': '请重新发送消息。',
    'chat.historyLoadFailed': '聊天记录加载失败',
    'chat.deleteMessage': '删除这条消息',
    'chat.messageDeleted': '消息已删除',
    'chat.deleteFailed': '删除消息失败',
    'chat.clearHistory': '清空聊天记录',
    'chat.historyCleared': '聊天记录已清空',
    'chat.clearHistoryFailed': '清空聊天记录失败',
    'chat.voiceUnavailable': '当前浏览器不支持语音输入',
    'chat.voiceFailed': '语音输入失败',
    'chat.voiceFailedDescription': '请重新录音再试一次。',
    'memories.title': '记忆',
    'memories.eyebrow': '记忆工作台',
    'memories.heading': '长期记忆看板',
    'memories.description': '这里会展示长期记忆、标签、召回置信度和索引状态。',
    'memories.pendingTitle': '记忆同步中',
    'memories.pendingDescription': '当后端写入对话记忆后，摘要、标签和召回线索会显示在这里。',
    'memories.emptyEyebrow': '空状态',
    'memories.emptyTitle': '暂时没有记忆条目',
    'memories.emptyDescription': '继续与 Arua 对话后，稳定偏好、重要计划和情绪线索会沉淀为长期记忆。',
    'memories.refresh': '刷新记忆',
    'memories.clearAll': '清空记忆',
    'memories.delete': '删除记忆',
    'memories.deleted': '记忆已删除',
    'memories.deleteFailed': '删除记忆失败',
    'memories.cleared': '长期记忆已清空',
    'memories.clearFailed': '清空长期记忆失败',
    'memories.loadFailed': '记忆加载失败',
    'memories.loading': '正在加载记忆...',
    'memories.untitled': '未命名记忆',
    'memories.total': '共 {count} 条记忆',
    'settings.title': '设置',
    'settings.accountOverview': '账号概览',
    'settings.userProfile': '用户资料',
    'settings.displayName': '显示名称',
    'settings.email': '邮箱地址',
    'settings.displayNamePlaceholder': '将从后端用户资料读取',
    'settings.emailPlaceholder': '将从后端账号读取',
    'settings.profileHint': '资料接口接入后，这里会保存昵称、语言和边界偏好。',
    'settings.saveProfile': '保存资料',
    'settings.language': '语言',
    'settings.languageHint': '切换后会立即应用到当前浏览器。',
    'settings.appearance': '外观',
    'settings.security': '安全与账号',
    'settings.sessions': '会话控制',
    'settings.sessionsHint': '退出登录会清空本地登录态并返回登录页。',
    'settings.signOut': '退出登录',
    'settings.dangerZone': '危险操作',
    'settings.dangerHint': '注销账号需要完整的权限确认、导出和审计流程。',
    'settings.deleteAccount': '注销账号',
    'settings.notReady': '这个功能还在接入中',
    'settings.notReadyDescription': '需要后端权限和审计接口完成后再开放。',
    'appearance.toggle': '切换外观',
    'appearance.dark': '深色模式',
    'appearance.light': '浅色模式',
    'appearance.darkDescription': '适合长时间对话的深色界面。',
    'appearance.lightDescription': '更明亮，但保留柔和的 Aura 色彩。',
    'auth.login': '登录',
    'auth.register': '注册',
    'auth.usernameLogin': '请输入用户名',
    'auth.usernameRegister': '设置用户名',
    'auth.passwordLogin': '请输入密码',
    'auth.passwordRegister': '设置密码',
    'auth.email': 'you@example.com',
    'auth.age': '请输入年龄',
    'auth.male': '男',
    'auth.female': '女',
    'auth.rememberMe': '记住我',
    'auth.forgotPassword': '忘记密码？',
    'auth.forgotPasswordPending': '密码找回暂未开放',
    'auth.forgotPasswordDescription': '需要短信或邮箱验证码接口接入后再开放。',
    'auth.signIn': '登录',
    'auth.createAccount': '创建账号',
    'auth.accountCreated': '账号已创建',
    'auth.registrationFailed': '注册失败',
    'auth.loginFailed': '登录失败',
    'auth.success': '登录成功',
    'auth.verifyRegister': '请检查注册信息后重试。',
    'auth.verifyLogin': '请检查账号密码后重试。',
    'auth.protected': '已启用安全加密保护。',
    'auth.termsPrefix': '继续使用即代表你同意',
    'auth.terms': '服务条款',
    'theme.toggle': '切换主题',
    'theme.light': '浅色',
    'theme.dark': '深色',
    'theme.system': '跟随系统',
  },
  'en-US': {
    'app.companionConsole': 'Companion console',
    'app.description': 'A calm AI workspace for conversation, memory, and personal tuning.',
    'app.navigate': 'Navigate',
    'nav.chat': 'AI Chat',
    'nav.memories': 'Memories',
    'nav.settings': 'Settings',
    'account.name': 'User Account',
    'account.status': 'Awaiting backend sync',
    'account.description':
      'Profile details, preferences, and companion permissions will appear here after the account service is connected.',
    'chat.placeholder': 'Message Arua...',
    'chat.uploadImage': 'Upload image',
    'chat.startVoice': 'Start voice input',
    'chat.stopVoice': 'Stop voice input',
    'chat.send': 'Send message',
    'chat.emotion': 'Emotion',
    'chat.emotionUpdated': 'Emotion updated',
    'chat.accountSyncFailed': 'Account sync failed',
    'chat.accountSyncFailedDescription': 'Please check whether the BFF service is running.',
    'chat.streamFailed': 'Message stream failed',
    'chat.invalidChunk': 'Arua returned an invalid stream chunk.',
    'chat.tryAgain': 'Please try sending your message again.',
    'chat.historyLoadFailed': 'Failed to load chat history',
    'chat.deleteMessage': 'Delete this message',
    'chat.messageDeleted': 'Message deleted',
    'chat.deleteFailed': 'Failed to delete message',
    'chat.clearHistory': 'Clear chat history',
    'chat.historyCleared': 'Chat history cleared',
    'chat.clearHistoryFailed': 'Failed to clear chat history',
    'chat.voiceUnavailable': 'Voice input unavailable',
    'chat.voiceFailed': 'Voice input failed',
    'chat.voiceFailedDescription': 'Please try recording again.',
    'memories.title': 'Memories',
    'memories.eyebrow': 'Memory workspace',
    'memories.heading': 'Long-term memory board',
    'memories.description':
      'Long-term memory records, tags, recall confidence, and indexing status will appear here.',
    'memories.pendingTitle': 'Memory sync pending',
    'memories.pendingDescription':
      'When the backend writes chat memories, summaries, tags, and recall cues will appear here.',
    'memories.emptyEyebrow': 'Empty state',
    'memories.emptyTitle': 'No memory entries yet',
    'memories.emptyDescription':
      'Keep talking with Arua and stable preferences, important plans, and emotional cues will become long-term memories.',
    'memories.refresh': 'Refresh memories',
    'memories.clearAll': 'Clear memories',
    'memories.delete': 'Delete memory',
    'memories.deleted': 'Memory deleted',
    'memories.deleteFailed': 'Failed to delete memory',
    'memories.cleared': 'Long-term memories cleared',
    'memories.clearFailed': 'Failed to clear long-term memories',
    'memories.loadFailed': 'Failed to load memories',
    'memories.loading': 'Loading memories...',
    'memories.untitled': 'Untitled memory',
    'memories.total': '{count} memories',
    'settings.title': 'Settings',
    'settings.accountOverview': 'Account overview',
    'settings.userProfile': 'User profile',
    'settings.displayName': 'Display name',
    'settings.email': 'Email address',
    'settings.displayNamePlaceholder': 'Will load from backend profile',
    'settings.emailPlaceholder': 'Will load from backend account',
    'settings.profileHint':
      'After the profile API is connected, nickname, language, and boundary preferences can be saved here.',
    'settings.saveProfile': 'Save profile',
    'settings.language': 'Language',
    'settings.languageHint': 'Changes apply immediately in this browser.',
    'settings.appearance': 'Appearance',
    'settings.security': 'Security & account',
    'settings.sessions': 'Session controls',
    'settings.sessionsHint': 'Signing out clears the local session and returns to login.',
    'settings.signOut': 'Sign out',
    'settings.dangerZone': 'Danger zone',
    'settings.dangerHint':
      'Account deletion needs permission confirmation, export, and audit flows.',
    'settings.deleteAccount': 'Delete account',
    'settings.notReady': 'This feature is still being connected',
    'settings.notReadyDescription':
      'It will be enabled after permission and audit APIs are ready.',
    'appearance.toggle': 'Toggle appearance',
    'appearance.dark': 'Dark mode',
    'appearance.light': 'Light mode',
    'appearance.darkDescription': 'Deep surfaces for long conversation sessions.',
    'appearance.lightDescription': 'Brighter surfaces with the same calm Aura palette.',
    'auth.login': 'Login',
    'auth.register': 'Register',
    'auth.usernameLogin': 'Enter your username',
    'auth.usernameRegister': 'Choose a username',
    'auth.passwordLogin': 'Enter your password',
    'auth.passwordRegister': 'Create a password',
    'auth.email': 'you@example.com',
    'auth.age': 'Enter your age',
    'auth.male': 'Male',
    'auth.female': 'Female',
    'auth.rememberMe': 'Remember me',
    'auth.forgotPassword': 'Forgot password?',
    'auth.forgotPasswordPending': 'Password recovery is not available yet',
    'auth.forgotPasswordDescription':
      'It will be enabled after SMS or email verification APIs are connected.',
    'auth.signIn': 'Sign In',
    'auth.createAccount': 'Create Account',
    'auth.accountCreated': 'Account created',
    'auth.registrationFailed': 'Registration failed',
    'auth.loginFailed': 'Login failed',
    'auth.success': 'Success',
    'auth.verifyRegister': 'Please verify your registration information and try again.',
    'auth.verifyLogin': 'Please verify your account information and try again.',
    'auth.protected': 'Protected by secure encryption.',
    'auth.termsPrefix': 'By continuing, you agree to our',
    'auth.terms': 'Terms of Service',
    'theme.toggle': 'Toggle theme',
    'theme.light': 'Light',
    'theme.dark': 'Dark',
    'theme.system': 'System',
  },
} satisfies Record<Locale, Record<string, string>>

type I18nContextValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: keyof (typeof messages)['en-US']) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('zh-CN')

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'zh-CN' || stored === 'en-US') {
      setLocaleState(stored)
      document.documentElement.lang = stored
    }
  }, [])

  const value = useMemo<I18nContextValue>(() => {
    const setLocale = (nextLocale: Locale) => {
      setLocaleState(nextLocale)
      window.localStorage.setItem(STORAGE_KEY, nextLocale)
      document.documentElement.lang = nextLocale
    }

    return {
      locale,
      setLocale,
      t: (key) => messages[locale][key] ?? messages['en-US'][key] ?? String(key),
    }
  }, [locale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider')
  }
  return context
}
