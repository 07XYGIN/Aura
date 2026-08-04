'use client'

import { useCallback, useEffect, useId, useMemo, useRef, useState, type ChangeEvent } from 'react'
import {
    Check,
    Copy,
    ImagePlus,
    Mic,
    Paperclip,
    RefreshCw,
    SendHorizontal,
    Square,
    ThumbsDown,
    Trash2,
    X,
} from 'lucide-react'
import { AruaAppShell } from '@/components/arua/app-shell'
import { ChatAttachmentPreview } from '@/components/arua/chat-attachment-preview'
import { ChatMessageContent } from '@/components/arua/chat-message-content'
import { Live2DStage } from '@/components/arua/live2d-stage'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { UseSse } from '@ai-web/utils/main'
import { cn } from '@/lib/utils'
import { copyTextToClipboard } from '@/lib/clipboard'
import { getCurrentUserId } from '@/lib/current-user'
import { getPythonApiBaseUrl } from '@/lib/python-request'
import type {
    BrowserSpeechRecognition,
    ChatAttachment,
    ChatMessage,
    Live2DPresence,
} from '@/types/arua'
import { toast } from 'sonner'
import { useUserStore } from '@/store/user'
import { useI18n } from '@/lib/i18n'
import {
    aura,
    type AuraHistoryMessage,
    type AuraReplyFeedbackCategory,
    type AuraUploadedAttachment,
    type AuraUploadAttachmentInput,
} from '@/apis/aura'

type ChatStreamChunk = {
    content?: string
    event?: string
    presence?: Live2DPresence
    messageId?: string
    batchId?: string
    batchIndex?: number
    batchTotal?: number
    delayMs?: number
    sentAt?: string
}

const MAX_ATTACHMENTS_PER_MESSAGE = 4
const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
const ACCEPTED_ATTACHMENT_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif'])
const MIN_ASSISTANT_DELAY_MS = 500
const MAX_ASSISTANT_DELAY_MS = 2500
const SPEECH_RECOGNITION_LANG = {
    'zh-CN': 'zh-CN',
    'en-US': 'en-US',
    'ja-JP': 'ja-JP',
} as const
const CITY_ADCODE_CACHE_KEY = 'aura_city_adcode'
const CITY_ADCODE_CACHE_TTL_MS = 24 * 60 * 60 * 1000
const WEATHER_QUERY_PATTERN =
    /天气|气温|温度|下雨|降雨|风力|冷不冷|热不热|weather|temperature|rain|wind/i

type CachedCityAdcode = {
    adcode: string
    expiresAt: number
}

const readCachedCityAdcode = () => {
    if (typeof window === 'undefined') {
        return null
    }

    try {
        const raw = window.localStorage.getItem(CITY_ADCODE_CACHE_KEY)
        if (!raw) {
            return null
        }

        const cached = JSON.parse(raw) as CachedCityAdcode
        if (!cached.adcode || cached.expiresAt <= Date.now()) {
            window.localStorage.removeItem(CITY_ADCODE_CACHE_KEY)
            return null
        }

        return cached.adcode
    } catch {
        return null
    }
}

const cacheCityAdcode = (adcode: string) => {
    if (typeof window === 'undefined' || !adcode) {
        return
    }

    window.localStorage.setItem(
        CITY_ADCODE_CACHE_KEY,
        JSON.stringify({
            adcode,
            expiresAt: Date.now() + CITY_ADCODE_CACHE_TTL_MS,
        }),
    )
}

const getBrowserPosition = () =>
    new Promise<GeolocationPosition>((resolve, reject) => {
        if (typeof navigator === 'undefined' || !navigator.geolocation) {
            reject(new Error('Geolocation is not available'))
            return
        }

        navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: false,
            maximumAge: CITY_ADCODE_CACHE_TTL_MS,
            timeout: 5000,
        })
    })

const createSessionId = () => {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
        return crypto.randomUUID()
    }

    const hex = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16))
    hex[12] = '4'
    hex[16] = ((Number.parseInt(hex[16], 16) & 0x3) | 0x8).toString(16)

    return [
        hex.slice(0, 8).join(''),
        hex.slice(8, 12).join(''),
        hex.slice(12, 16).join(''),
        hex.slice(16, 20).join(''),
        hex.slice(20, 32).join(''),
    ].join('-')
}

const readFileAsBase64 = (file: File) =>
    new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => {
            const result = reader.result
            if (typeof result !== 'string') {
                reject(new Error('Invalid file result'))
                return
            }
            resolve(result)
        }
        reader.onerror = () => reject(reader.error ?? new Error('File read failed'))
        reader.readAsDataURL(file)
    })

const wait = (delayMs: number) =>
    new Promise<void>((resolve) => {
        window.setTimeout(resolve, delayMs)
    })

const normalizeAssistantDelay = (value?: number) => {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return MIN_ASSISTANT_DELAY_MS
    }

    return Math.min(MAX_ASSISTANT_DELAY_MS, Math.max(MIN_ASSISTANT_DELAY_MS, value))
}

const isAcceptedAttachment = (file: File) => ACCEPTED_ATTACHMENT_TYPES.has(file.type)

const getAttachmentIcon = () => ImagePlus

const buildUploadPayload = async (files: File[]): Promise<AuraUploadAttachmentInput[]> =>
    Promise.all(
        files.map(async (file) => ({
            fileName: file.name,
            contentType: file.type,
            size: file.size,
            dataBase64: await readFileAsBase64(file),
        })),
    )

const normalizeChatAttachments = (
    attachments: AuraHistoryMessage['attachments'],
): ChatAttachment[] => {
    if (!Array.isArray(attachments)) {
        return []
    }

    return attachments.flatMap((attachment) => {
        if (typeof attachment === 'string') {
            return [{ fileName: attachment }]
        }
        if (!attachment || typeof attachment.fileName !== 'string') {
            return []
        }
        return [
            {
                id: attachment.id,
                fileName: attachment.fileName,
                contentType: attachment.contentType,
                size: attachment.size,
            },
        ]
    })
}

const mapHistoryMessage = (item: AuraHistoryMessage, index: number): ChatMessage | null => {
    if (!item.content) {
        return null
    }

    const role = item.senderType ?? (item.role === 'aura' ? 'assistant' : item.role)

    if (role !== 'user' && role !== 'assistant') {
        return null
    }

    return {
        id: item.id ?? `history-${index}-${role}`,
        sessionId: item.sessionId,
        role,
        content: item.content,
        attachments: normalizeChatAttachments(item.attachments),
        createdAt: item.createdAt,
        turnId: item.turnId,
        batchId: item.batchId,
        batchIndex: item.batchIndex,
        batchTotal: item.batchTotal,
    }
}

const buildChatSseUrl = () => {
    return `${getPythonApiBaseUrl()}/api/send/sse/`
}

export function AruaChatScreen() {
    const { locale, t } = useI18n()
    const inputId = useId()
    const fileInputRef = useRef<HTMLInputElement>(null)
    const messagesRef = useRef<HTMLDivElement>(null)
    const recognitionRef = useRef<BrowserSpeechRecognition | null>(null)
    const isSendingRef = useRef(false)
    const assistantDeliveryQueueRef = useRef<Promise<void>>(Promise.resolve())
    const pendingAssistantMessageIdRef = useRef<string | null>(null)
    const currentSessionIdRef = useRef(createSessionId())
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [message, setMessage] = useState('')
    const [isListening, setIsListening] = useState(false)
    const [isStreaming, setIsStreaming] = useState(false)
    const [selectedFiles, setSelectedFiles] = useState<File[]>([])
    const [latestPresence, setLatestPresence] = useState<Live2DPresence | null>(null)
    const [replyFeedbackMenuMessageId, setReplyFeedbackMenuMessageId] = useState<string | null>(
        null,
    )
    const [feedbackMessageIds, setFeedbackMessageIds] = useState<Set<string>>(() => new Set())
    const [isAssistantTyping, setIsAssistantTyping] = useState(false)
    const [deletingMessageId, setDeletingMessageId] = useState<string | null>(null)
    const [isClearingHistory, setIsClearingHistory] = useState(false)
    const [cityAdcode, setCityAdcode] = useState<string | null>(() => readCachedCityAdcode())
    const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
    const token = useUserStore((state) => state.token)
    const getUserInfo = useUserStore((state) => state.getUserInfo)
    const loadHistoryMessages = useCallback(
        async (options?: {
            showError?: boolean
            cancelled?: () => boolean
        }) => {
            if (!token) {
                return
            }

            try {
                const response = await aura.getCurrentMessages()

                if (options?.cancelled?.()) {
                    return
                }

                const historyMessages = (response.data ?? [])
                    .map(mapHistoryMessage)
                    .filter((item): item is ChatMessage => Boolean(item))

                setMessages(historyMessages)
            } catch {
                if (options?.cancelled?.()) {
                    return
                }

                if (options?.showError === false) {
                    return
                }

                toast.error(t('chat.historyLoadFailed'), {
                    description: t('chat.tryAgain'),
                    position: 'top-center',
                })
            }
        },
        [t, token],
    )

    useEffect(() => {
        if (!token) {
            return
        }

        getUserInfo().catch(() => {
            toast.error(t('chat.accountSyncFailed'), {
                description: t('chat.accountSyncFailedDescription'),
                position: 'top-center',
            })
        })
        aura.getMemoryRetention()
            .then((response) => {
                const retention = response.data
                if (!retention || retention.permanent || !retention.shouldPrompt) {
                    return
                }

                if (retention.paywall) {
                    toast('Aura 还想继续记住你的心事。', {
                        description: '开通永久记忆后，之前的记忆会重新回来。',
                        position: 'top-center',
                    })
                    return
                }

                toast(`Aura 还能记住你的心事 ${retention.daysRemaining} 天……`, {
                    description: '我会先把重要的东西轻轻收好。',
                    position: 'top-center',
                })
            })
            .catch(() => undefined)
    }, [getUserInfo, t, token])
    useEffect(() => {
        if (!token) {
            return
        }

        let cancelled = false

        void loadHistoryMessages({
            cancelled: () => cancelled,
        })

        return () => {
            cancelled = true
        }
    }, [loadHistoryMessages, token])
    useEffect(() => {
        messagesRef.current?.scrollTo({
            top: messagesRef.current.scrollHeight,
            behavior: 'smooth',
        })
    }, [messages])
    const enqueueAssistantMessage = useCallback((payload: ChatStreamChunk) => {
        const content = payload.content?.trim()
        if (!content) {
            return
        }

        const delayMs = normalizeAssistantDelay(payload.delayMs)
        assistantDeliveryQueueRef.current = assistantDeliveryQueueRef.current
            .catch(() => undefined)
            .then(async () => {
                setIsAssistantTyping(true)
                await wait(delayMs)
                setMessages((currentMessages) => {
                    const pendingId = pendingAssistantMessageIdRef.current
                    const pendingIndex = pendingId
                        ? currentMessages.findIndex((item) => item.id === pendingId && item.pending)
                        : -1

                    const nextMessage: ChatMessage = {
                        id:
                            payload.messageId ??
                            `assistant-${payload.batchId ?? Date.now()}-${payload.batchIndex ?? currentMessages.length}`,
                        sessionId: currentSessionIdRef.current,
                        role: 'assistant',
                        content,
                        pending: false,
                        createdAt: payload.sentAt,
                        batchId: payload.batchId,
                        batchIndex: payload.batchIndex,
                        batchTotal: payload.batchTotal,
                    }

                    if (pendingIndex >= 0) {
                        pendingAssistantMessageIdRef.current = null
                        return currentMessages.map((item, index) =>
                            index === pendingIndex ? nextMessage : item,
                        )
                    }

                    return [...currentMessages, nextMessage]
                })
                setIsAssistantTyping(false)
            })
    }, [])
    const finishStreamAfterDelivered = useCallback(() => {
        void assistantDeliveryQueueRef.current
            .catch(() => undefined)
            .then(() => {
                isSendingRef.current = false
                setIsStreaming(false)
                setIsAssistantTyping(false)
                void loadHistoryMessages({ showError: false })
            })
    }, [loadHistoryMessages])
    const { connect, disconnect } = useMemo(
        () =>
            UseSse(buildChatSseUrl(), {
                headers: token ? { Authorization: `Bearer ${token}` } : undefined,
                onMessage: (data) => {
                    if (data === '[DONE]') {
                        finishStreamAfterDelivered()
                        return
                    }

                    let parsed: ChatStreamChunk

                    try {
                        parsed = JSON.parse(data) as ChatStreamChunk
                    } catch {
                        toast.error(t('chat.streamFailed'), {
                            description: t('chat.invalidChunk'),
                            position: 'top-center',
                        })
                        return
                    }

                    if (parsed.event === 'live2d_state' && parsed.presence) {
                        setLatestPresence(parsed.presence)
                        return
                    }

                    if (parsed.event === 'assistant_message') {
                        enqueueAssistantMessage(parsed)
                        return
                    }

                    const content = parsed.content ?? ''
                    if (!content) {
                        return
                    }

                    setMessages((currentMessages) =>
                        currentMessages.map((item, index) => {
                            const isLastMessage = index === currentMessages.length - 1
                            const isStreamingAssistant = isLastMessage && item.role === 'assistant'

                            if (!isStreamingAssistant) {
                                return item
                            }

                            return {
                                ...item,
                                content: item.content + content,
                                pending: false,
                            }
                        }),
                    )
                },
                onError: () => {
                    isSendingRef.current = false
                    setIsStreaming(false)
                    setIsAssistantTyping(false)
                    const pendingId = pendingAssistantMessageIdRef.current
                    if (pendingId) {
                        pendingAssistantMessageIdRef.current = null
                        setMessages((currentMessages) =>
                            currentMessages.filter((item) => item.id !== pendingId),
                        )
                    }
                    toast.error(t('chat.streamFailed'), {
                        description: t('chat.tryAgain'),
                        position: 'top-center',
                    })
                },
                onClose: () => {
                    if (isSendingRef.current) {
                        finishStreamAfterDelivered()
                    }
                },
            }),
        [enqueueAssistantMessage, finishStreamAfterDelivered, loadHistoryMessages, t, token],
    )
    useEffect(() => {
        return () => {
            disconnect()
        }
    }, [disconnect])
    useEffect(() => {
        if (!isStreaming) {
            disconnect()
        }
    }, [disconnect, isStreaming])
    const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(event.target.files ?? [])
        const validFiles = files.filter(isAcceptedAttachment)
        const oversized = validFiles.find((file) => file.size > MAX_ATTACHMENT_BYTES)

        if (files.length !== validFiles.length) {
            toast.error('不支持的图片格式', {
                description: '仅支持 PNG、JPG、WebP 和 GIF 图片。',
                position: 'top-center',
            })
        }

        if (oversized) {
            toast.error('Attachment is too large', {
                description: 'Each attachment must be 10MB or smaller.',
                position: 'top-center',
            })
        }

        setSelectedFiles(
            validFiles
                .filter((file) => file.size <= MAX_ATTACHMENT_BYTES)
                .slice(0, MAX_ATTACHMENTS_PER_MESSAGE),
        )
    }

    const handleMessageChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
        setMessage(event.target.value)
    }

    const handleVoiceInput = () => {
        if (isListening) {
            recognitionRef.current?.stop()
            return
        }

        const SpeechRecognition = window.SpeechRecognition ?? window.webkitSpeechRecognition

        if (!SpeechRecognition) {
            toast.error(t('chat.voiceUnavailable'), {
                description: 'This browser does not support speech recognition.',
                position: 'top-center',
            })
            return
        }

        const recognition = new SpeechRecognition()
        recognition.lang = SPEECH_RECOGNITION_LANG[locale]
        recognition.continuous = false
        recognition.interimResults = false

        recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map((result) => result[0]?.transcript ?? '')
                .join('')
                .trim()

            if (transcript) {
                setMessage((prev) => [prev.trim(), transcript].filter(Boolean).join('\n'))
            }
        }

        recognition.onerror = () => {
            toast.error(t('chat.voiceFailed'), {
                description: t('chat.voiceFailedDescription'),
                position: 'top-center',
            })
            setIsListening(false)
        }

        recognition.onend = () => {
            setIsListening(false)
        }

        recognitionRef.current = recognition
        setIsListening(true)
        recognition.start()
    }

    const uploadSelectedFiles = async (files: File[]): Promise<AuraUploadedAttachment[]> => {
        if (files.length === 0) {
            return []
        }

        const payload = await buildUploadPayload(files)
        const response = await aura.uploadAttachments(payload)
        const uploaded = response.data?.items ?? []
        if (uploaded.length !== files.length) {
            throw new Error('Attachment upload was incomplete')
        }
        return uploaded
    }

    const resolveCityAdcodeForChat = useCallback(
        async (allowBrowserLocation: boolean) => {
            if (cityAdcode) {
                return cityAdcode
            }

            const cached = readCachedCityAdcode()
            if (cached) {
                setCityAdcode(cached)
                return cached
            }

            if (allowBrowserLocation) {
                try {
                    const position = await getBrowserPosition()
                    const response = await aura.resolveCityAdcode({
                        longitude: position.coords.longitude,
                        latitude: position.coords.latitude,
                    })
                    const resolved = response.data?.adcode
                    if (resolved) {
                        cacheCityAdcode(resolved)
                        setCityAdcode(resolved)
                        return resolved
                    }
                } catch {
                    // Location is optional. If it fails, Aura will ask for a city before using weather.
                }
            }

            try {
                const response = await aura.resolveCityAdcode()
                const resolved = response.data?.adcode
                if (resolved) {
                    cacheCityAdcode(resolved)
                    setCityAdcode(resolved)
                    return resolved
                }
            } catch {
                return null
            }

            return null
        },
        [cityAdcode],
    )

    const handleSubmit = async () => {
        if (isSendingRef.current || isStreaming) {
            return
        }

        const trimmedMessage = message.trim()

        if (!trimmedMessage && selectedFiles.length === 0) {
            return
        }

        const userId = getCurrentUserId()
        if (!userId) {
            toast.error(t('chat.accountSyncFailed'), {
                description: t('chat.accountSyncFailedDescription'),
                position: 'top-center',
            })
            return
        }

        const now = Date.now()
        const clientMessageId = `client-${now}-${Math.random().toString(36).slice(2, 10)}`
        const assistantMessageId = `assistant-${now}`
        const sessionId = currentSessionIdRef.current
        isSendingRef.current = true
        pendingAssistantMessageIdRef.current = assistantMessageId
        assistantDeliveryQueueRef.current = Promise.resolve()
        setIsStreaming(true)
        setLatestPresence({ expression: 'thinking', motion: 'idle', intensity: 1 })
        setIsAssistantTyping(true)

        const shouldResolveCityAdcode = WEATHER_QUERY_PATTERN.test(trimmedMessage)
        const cityAdcodeForMessage = shouldResolveCityAdcode
            ? await resolveCityAdcodeForChat(true)
            : cityAdcode

        let uploadedAttachments: AuraUploadedAttachment[] = []
        try {
            uploadedAttachments = await uploadSelectedFiles(selectedFiles)
        } catch (error) {
            isSendingRef.current = false
            pendingAssistantMessageIdRef.current = null
            setIsStreaming(false)
            setIsAssistantTyping(false)
            toast.error('Attachment upload failed', {
                description: error instanceof Error ? error.message : t('chat.tryAgain'),
                position: 'top-center',
            })
            return
        }

        setMessages((currentMessages) => [
            ...currentMessages,
            {
                id: `local-${now}`,
                sessionId,
                role: 'user',
                content: trimmedMessage,
                attachments: uploadedAttachments.map((file) => ({
                    id: file.id,
                    fileName: file.fileName,
                    contentType: file.contentType,
                    size: file.size,
                })),
            },
            {
                id: assistantMessageId,
                sessionId,
                role: 'assistant',
                content: '',
                pending: true,
            },
        ])
        setMessage('')
        setSelectedFiles([])

        if (fileInputRef.current) {
            fileInputRef.current.value = ''
        }

        connect({
            body: JSON.stringify({
                clientMessageId,
                userId,
                sessionId,
                message: trimmedMessage,
                attachmentIds: uploadedAttachments.map((file) => file.id),
                cityAdcode: cityAdcodeForMessage || undefined,
            }),
        })
    }

    const handleReplyFeedback = async (
        chatMessage: ChatMessage,
        category: AuraReplyFeedbackCategory,
    ) => {
        if (
            feedbackMessageIds.has(chatMessage.id) ||
            chatMessage.id.startsWith('local-') ||
            chatMessage.id.startsWith('assistant-')
        ) {
            return
        }

        try {
            await aura.submitReplyFeedback(chatMessage.id, category)
            setFeedbackMessageIds((current) => {
                const next = new Set(current)
                next.add(chatMessage.id)
                return next
            })
            setReplyFeedbackMenuMessageId(null)
            toast.success(category === 'helpful' ? '收到。' : '我会按这个方向调整。', {
                position: 'top-center',
            })
        } catch {
            toast.error('反馈没有保存成功', {
                description: t('chat.tryAgain'),
                position: 'top-center',
            })
        }
    }

    const handleRetryReply = (chatMessage: ChatMessage) => {
        if (
            isSendingRef.current ||
            isStreaming ||
            chatMessage.id.startsWith('local-') ||
            chatMessage.id.startsWith('assistant-')
        ) {
            return
        }
        const userId = getCurrentUserId()
        if (!userId) {
            return
        }

        const now = Date.now()
        const assistantMessageId = `assistant-retry-${now}`
        isSendingRef.current = true
        pendingAssistantMessageIdRef.current = assistantMessageId
        assistantDeliveryQueueRef.current = Promise.resolve()
        setIsStreaming(true)
        setIsAssistantTyping(true)
        setLatestPresence({ expression: 'thinking', motion: 'idle', intensity: 1 })
        setMessages((current) => [
            ...current,
            { id: assistantMessageId, role: 'assistant', content: '', pending: true },
        ])
        connect({
            body: JSON.stringify({
                userId,
                message: '',
                retryMessageId: chatMessage.id,
            }),
        })
    }

    const handleCopyMessage = async (chatMessage: ChatMessage) => {
        if (!chatMessage.content) {
            return
        }

        try {
            await copyTextToClipboard(chatMessage.content)
            setCopiedMessageId(chatMessage.id)
            window.setTimeout(() => {
                setCopiedMessageId((currentId) => (currentId === chatMessage.id ? null : currentId))
            }, 1400)
            toast.success('已复制消息', {
                position: 'top-center',
            })
        } catch {
            toast.error('复制失败', {
                position: 'top-center',
            })
        }
    }

    const handleDeleteMessage = async (messageId: string) => {
        if (isStreaming || deletingMessageId) {
            return
        }

        setDeletingMessageId(messageId)

        try {
            if (!messageId.startsWith('local-') && !messageId.startsWith('assistant-')) {
                await aura.deleteCurrentMessage(messageId)
            }

            setMessages((currentMessages) =>
                currentMessages.filter((chatMessage) => chatMessage.id !== messageId),
            )
            toast.success(t('chat.messageDeleted'), {
                position: 'top-center',
            })
        } catch {
            toast.error(t('chat.deleteFailed'), {
                description: t('chat.tryAgain'),
                position: 'top-center',
            })
        } finally {
            setDeletingMessageId(null)
        }
    }

    const handleClearHistory = async () => {
        if (isStreaming || isClearingHistory || messages.length === 0) {
            return
        }

        setIsClearingHistory(true)

        try {
            await aura.clearCurrentMessages()
            setMessages([])
            setLatestPresence(null)
            setIsAssistantTyping(false)
            pendingAssistantMessageIdRef.current = null
            assistantDeliveryQueueRef.current = Promise.resolve()
            currentSessionIdRef.current = createSessionId()
            toast.success(t('chat.historyCleared'), {
                position: 'top-center',
            })
        } catch {
            toast.error(t('chat.clearHistoryFailed'), {
                description: t('chat.tryAgain'),
                position: 'top-center',
            })
        } finally {
            setIsClearingHistory(false)
        }
    }

    return (
        <AruaAppShell
            active="chat"
            hideHeader
            showDefaultAction={false}
            title={null}
            contentClassName="relative min-h-0 flex-1 overflow-hidden p-0 sm:p-0 lg:p-0"
        >
            <section className="absolute inset-0 grid min-h-0 w-full grid-rows-[auto_minmax(0,1fr)] overflow-hidden bg-[color-mix(in_srgb,var(--aura-surface-solid)_70%,transparent)] lg:grid-cols-[minmax(24rem,44%)_minmax(0,1fr)] lg:grid-rows-1">
                <aside className="min-h-0 border-b border-[var(--aura-border)] p-4 lg:border-r lg:border-b-0 lg:p-5">
                    <Live2DStage
                        className="h-[22rem] lg:h-full lg:min-h-[calc(100vh-2.5rem)]"
                        isActive={isStreaming || isAssistantTyping}
                        emotionLabel={isStreaming || isAssistantTyping ? t('chat.replying') : t('chat.present')}
                        presence={latestPresence}
                        labels={{
                            presence: t('chat.presence'),
                            subtitle: t('chat.presenceSubtitle'),
                            ready: t('chat.present'),
                            loading: t('chat.presenceLoading'),
                            play: t('chat.presenceRespond'),
                            unavailable: t('chat.presenceUnavailable'),
                        }}
                    />
                </aside>

                <div className="relative flex min-h-0 flex-col overflow-hidden">
                    <div
                        ref={messagesRef}
                        className={cn(
                            'aura-scrollbar min-h-0 flex-1 overflow-y-auto px-4 pt-5 pb-56 sm:px-6 lg:px-8',
                        )}
                    >
                        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
                            {messages.map((chatMessage) => {
                                const isUser = chatMessage.role === 'user'
                                const feedbackRecorded = feedbackMessageIds.has(chatMessage.id)

                                return (
                                    <div
                                        key={chatMessage.id}
                                        className={cn(
                                            'group/message relative flex w-full',
                                            isUser ? 'justify-end' : 'justify-start',
                                        )}
                                    >
                                        <div
                                            className={cn(
                                                'max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-7 shadow-[0_18px_42px_-34px_var(--aura-glow)] sm:max-w-[72%]',
                                                isUser
                                                    ? 'bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-[#201733]'
                                                    : 'border border-[var(--aura-border)] bg-[var(--aura-surface)] text-[var(--aura-text)]',
                                            )}
                                        >
                                            {chatMessage.pending ? (
                                                <span
                                                    className="inline-flex items-center gap-1.5 py-1"
                                                    aria-label={
                                                        isAssistantTyping
                                                            ? 'Aura 正在输入'
                                                            : undefined
                                                    }
                                                >
                                                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--aura-text-muted)]" />
                                                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--aura-text-muted)] [animation-delay:120ms]" />
                                                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--aura-text-muted)] [animation-delay:240ms]" />
                                                </span>
                                            ) : chatMessage.content ? (
                                                <ChatMessageContent
                                                    content={chatMessage.content}
                                                    isUser={isUser}
                                                />
                                            ) : null}

                                            {chatMessage.attachments?.length ? (
                                                <div
                                                    className={cn(
                                                        'mt-3 flex flex-wrap gap-2',
                                                        isUser
                                                            ? 'text-[#201733]/78'
                                                            : 'text-[var(--aura-text-muted)]',
                                                    )}
                                                >
                                                    {chatMessage.attachments.map((attachment) => {
                                                        return (
                                                            <ChatAttachmentPreview
                                                                key={
                                                                    attachment.id ??
                                                                    attachment.fileName
                                                                }
                                                                attachment={attachment}
                                                                isUser={isUser}
                                                            />
                                                        )
                                                    })}
                                                </div>
                                            ) : null}
                                        </div>
                                        {!isUser && chatMessage.content ? (
                                            <>
                                                <div className="mx-1 flex self-center opacity-0 transition-opacity group-hover/message:opacity-100 focus-within:opacity-100">
                                                    <Button
                                                        type="button"
                                                        variant="ghost"
                                                        size="icon-xs"
                                                        disabled={isStreaming}
                                                        className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                                                        aria-label="重新生成回复"
                                                        title="重新生成回复"
                                                        onClick={() =>
                                                            handleRetryReply(chatMessage)
                                                        }
                                                    >
                                                        <RefreshCw className="h-3.5 w-3.5" />
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        variant="ghost"
                                                        size="icon-xs"
                                                        disabled={feedbackRecorded}
                                                        className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                                                        aria-label="纠正回复风格"
                                                        title="纠正回复风格"
                                                        onClick={() =>
                                                            setReplyFeedbackMenuMessageId(
                                                                chatMessage.id,
                                                            )
                                                        }
                                                    >
                                                        {feedbackRecorded ? (
                                                            <Check className="h-3.5 w-3.5" />
                                                        ) : (
                                                            <ThumbsDown className="h-3.5 w-3.5" />
                                                        )}
                                                    </Button>
                                                </div>
                                                {replyFeedbackMenuMessageId === chatMessage.id ? (
                                                    <div className="absolute top-full left-0 z-30 mt-1 flex max-w-[min(28rem,94vw)] flex-wrap gap-1 border border-[var(--aura-border)] bg-[var(--aura-surface-solid)] p-1.5 shadow-lg">
                                                        {[
                                                            ['too_long', '太长'],
                                                            ['too_preachy', '太说教'],
                                                            ['too_clingy', '太黏'],
                                                            ['too_many_questions', '追问多'],
                                                            ['wrong_context', '没接住'],
                                                        ].map(([category, label]) => (
                                                            <button
                                                                key={category}
                                                                type="button"
                                                                className="border border-transparent px-2 py-1 text-xs text-[var(--aura-text-muted)] transition hover:border-[var(--aura-border)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-text)]"
                                                                onClick={() =>
                                                                    handleReplyFeedback(
                                                                        chatMessage,
                                                                        category as AuraReplyFeedbackCategory,
                                                                    )
                                                                }
                                                            >
                                                                {label}
                                                            </button>
                                                        ))}
                                                        <button
                                                            type="button"
                                                            className="inline-flex h-7 w-7 items-center justify-center text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)]"
                                                            aria-label="关闭反馈选项"
                                                            title="关闭"
                                                            onClick={() =>
                                                                setReplyFeedbackMenuMessageId(null)
                                                            }
                                                        >
                                                            <X className="h-3.5 w-3.5" />
                                                        </button>
                                                    </div>
                                                ) : null}
                                            </>
                                        ) : null}
                                        {chatMessage.content ? (
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon-xs"
                                                className={cn(
                                                    'mx-1 self-center rounded-full text-[var(--aura-text-muted)] opacity-0 transition-opacity group-hover/message:opacity-100 hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)] focus-visible:opacity-100',
                                                    isUser ? 'order-first' : 'order-last',
                                                    copiedMessageId === chatMessage.id &&
                                                        'opacity-100',
                                                )}
                                                aria-label="复制消息"
                                                title={
                                                    copiedMessageId === chatMessage.id
                                                        ? '已复制'
                                                        : '复制消息'
                                                }
                                                onClick={() => handleCopyMessage(chatMessage)}
                                            >
                                                <Copy className="h-3.5 w-3.5" />
                                            </Button>
                                        ) : null}
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon-xs"
                                            disabled={
                                                isStreaming || deletingMessageId === chatMessage.id
                                            }
                                            className={cn(
                                                'mx-1 self-center rounded-full text-[var(--aura-text-muted)] opacity-0 transition-opacity group-hover/message:opacity-100 hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)] focus-visible:opacity-100',
                                                isUser ? 'order-first' : 'order-last',
                                            )}
                                            aria-label={t('chat.deleteMessage')}
                                            title={t('chat.deleteMessage')}
                                            onClick={() => handleDeleteMessage(chatMessage.id)}
                                        >
                                            <Trash2 className="h-3.5 w-3.5" />
                                        </Button>
                                    </div>
                                )
                            })}
                        </div>
                    </div>

                    <div className="absolute inset-x-0 bottom-0 flex flex-col items-center border-t border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-bg)_88%,transparent)] px-4 py-4 backdrop-blur-xl sm:px-6 lg:px-8">
                        <div className="w-full max-w-3xl rounded-[1.25rem] border border-[var(--aura-border)] bg-[var(--aura-surface)] p-3 shadow-[0_22px_64px_-46px_var(--aura-glow)]">
                            {selectedFiles.length > 0 ? (
                                <div className="mb-3 flex flex-wrap gap-2">
                                    {selectedFiles.map((file) => {
                                        const AttachmentIcon = getAttachmentIcon()

                                        return (
                                            <div
                                                key={`${file.name}-${file.lastModified}`}
                                                className="inline-flex max-w-full items-center gap-2 rounded-full bg-[var(--aura-surface-strong)] px-3 py-1.5 text-xs text-[var(--aura-text-muted)]"
                                            >
                                                <AttachmentIcon className="h-3.5 w-3.5 shrink-0 text-[var(--aura-primary)]" />
                                                <span className="truncate">{file.name}</span>
                                            </div>
                                        )
                                    })}
                                </div>
                            ) : null}

                            <Textarea
                                rows={3}
                                value={message}
                                onChange={handleMessageChange}
                                placeholder={t('chat.placeholder')}
                                className="aura-scrollbar min-h-24 resize-none border-0 bg-transparent px-1 py-1 text-sm leading-7 text-[var(--aura-text)] shadow-none ring-0 focus-visible:border-0 focus-visible:ring-0"
                            />

                            <div className="mt-3 flex items-end justify-between gap-3">
                                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                                    <input
                                        id={inputId}
                                        ref={fileInputRef}
                                        type="file"
                                        accept="image/jpeg,image/png,image/webp,image/gif"
                                        multiple
                                        className="hidden"
                                        onChange={handleFileChange}
                                    />
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                                        aria-label="上传图片"
                                        title="上传图片"
                                        onClick={() => fileInputRef.current?.click()}
                                    >
                                        <Paperclip className="h-4 w-4" />
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className={cn(
                                            'rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]',
                                            isListening &&
                                                'bg-[var(--aura-primary-soft)] text-[var(--aura-primary)]',
                                        )}
                                        aria-label={
                                            isListening ? t('chat.stopVoice') : t('chat.startVoice')
                                        }
                                        onClick={handleVoiceInput}
                                    >
                                        {isListening ? (
                                            <Square className="h-4 w-4" />
                                        ) : (
                                            <Mic className="h-4 w-4" />
                                        )}
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        disabled={
                                            isStreaming ||
                                            isClearingHistory ||
                                            messages.length === 0
                                        }
                                        className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                                        aria-label={t('chat.clearHistory')}
                                        title={t('chat.clearHistory')}
                                        onClick={handleClearHistory}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>

                                <Button
                                    type="button"
                                    size="icon-lg"
                                    disabled={
                                        isStreaming ||
                                        (!message.trim() && selectedFiles.length === 0)
                                    }
                                    className="rounded-full bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-[#201733] shadow-[0_18px_32px_-22px_var(--aura-glow)]"
                                    aria-label={t('chat.send')}
                                    onClick={handleSubmit}
                                >
                                    <SendHorizontal className="h-4 w-4 translate-x-0.5" />
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </AruaAppShell>
    )
}
