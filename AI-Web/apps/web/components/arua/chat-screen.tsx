'use client'

import { useCallback, useEffect, useId, useMemo, useRef, useState, type ChangeEvent } from 'react'
import {
    Copy,
    FileText,
    ImagePlus,
    Mic,
    Paperclip,
    SendHorizontal,
    Square,
    Star,
    Trash2,
} from 'lucide-react'
import { AruaAppShell } from '@/components/arua/app-shell'
import { ChatMessageContent } from '@/components/arua/chat-message-content'
import { Live2DStage } from '@/components/arua/live2d-stage'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { UseSse } from '@ai-web/utils/main'
import { cn } from '@/lib/utils'
import { copyTextToClipboard } from '@/lib/clipboard'
import { getCurrentUserId } from '@/lib/current-user'
import { getPythonApiBaseUrl } from '@/lib/python-request'
import type { BrowserSpeechRecognition, ChatMessage } from '@/types/arua'
import { toast } from 'sonner'
import { useUserStore } from '@/store/user'
import { useI18n } from '@/lib/i18n'
import {
    aura,
    type AuraEmotionReportPreview,
    type AuraHistoryMessage,
    type AuraUploadedAttachment,
    type AuraUploadAttachmentInput,
} from '@/apis/aura'

type EmotionPayload = {
    user_emotion?: string
    aura_mood?: string
    label?: string
    name?: string
    type?: string
    mood?: string
    confidence?: number
    score?: number
    valence?: number
    arousal?: number
    [key: string]: unknown
}

type ChatStreamChunk = {
    content?: string
    event?: string
    emotion?: EmotionPayload
    messageId?: string
    batchId?: string
    batchIndex?: number
    batchTotal?: number
    delayMs?: number
    sentAt?: string
}

const FEEDBACK_IDLE_DELAY_MS = 30_000
const MAX_ATTACHMENTS_PER_MESSAGE = 4
const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
const ACCEPTED_ATTACHMENT_TYPES = new Set([
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/gif',
    'text/plain',
    'text/markdown',
    'text/csv',
    'application/json',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])
const ACCEPTED_ATTACHMENT_EXTENSIONS = new Set([
    '.txt',
    '.md',
    '.markdown',
    '.csv',
    '.json',
    '.pdf',
    '.doc',
    '.docx',
])
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

const parseJsonArray = (value?: string) => {
    if (!value) {
        return []
    }

    try {
        const parsed = JSON.parse(value)
        return Array.isArray(parsed) ? parsed.map(String) : []
    } catch {
        return []
    }
}

const parseFullReport = (value?: string) => {
    if (!value) {
        return null
    }

    try {
        return JSON.parse(value) as {
            weeklyKeywords?: string[]
            patternAnalysis?: string[]
            auraObservation?: string
        }
    } catch {
        return null
    }
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

const isAcceptedAttachment = (file: File) => {
    if (ACCEPTED_ATTACHMENT_TYPES.has(file.type) || file.type.startsWith('image/')) {
        return true
    }

    const extension = file.name.includes('.')
        ? `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`
        : ''

    return ACCEPTED_ATTACHMENT_EXTENSIONS.has(extension)
}

const getAttachmentIcon = (fileName: string) => {
    const extension = fileName.includes('.')
        ? `.${fileName.split('.').pop()?.toLowerCase() ?? ''}`
        : ''

    return ACCEPTED_ATTACHMENT_EXTENSIONS.has(extension) ? FileText : ImagePlus
}

const buildUploadPayload = async (files: File[]): Promise<AuraUploadAttachmentInput[]> =>
    Promise.all(
        files.map(async (file) => ({
            fileName: file.name,
            contentType: file.type,
            size: file.size,
            dataBase64: await readFileAsBase64(file),
        })),
    )

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
        attachments: item.attachments,
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

const getEmotionLabel = (emotion: EmotionPayload) => {
    if (emotion.aura_mood || emotion.user_emotion) {
        return [
            emotion.aura_mood ? `Aura ${emotion.aura_mood}` : null,
            emotion.user_emotion ? `You ${emotion.user_emotion}` : null,
        ]
            .filter(Boolean)
            .join(' / ')
    }

    const label = emotion.label ?? emotion.name ?? emotion.type ?? emotion.mood

    if (label) {
        return label
    }

    return 'Emotion updated'
}

const getEmotionDetail = (emotion: EmotionPayload) => {
    const confidence = emotion.confidence ?? emotion.score

    if (typeof confidence === 'number') {
        return `${Math.round(confidence * 100)}%`
    }

    if (typeof emotion.valence === 'number') {
        return `Valence ${emotion.valence.toFixed(2)}`
    }

    if (typeof emotion.arousal === 'number') {
        return `Arousal ${emotion.arousal.toFixed(2)}`
    }

    return null
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
    const lastCompletedSessionIdRef = useRef<string | null>(null)
    const feedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [message, setMessage] = useState('')
    const [isListening, setIsListening] = useState(false)
    const [isStreaming, setIsStreaming] = useState(false)
    const [selectedFiles, setSelectedFiles] = useState<File[]>([])
    const [latestEmotion, setLatestEmotion] = useState<EmotionPayload | null>(null)
    const [isAssistantTyping, setIsAssistantTyping] = useState(false)
    const [deletingMessageId, setDeletingMessageId] = useState<string | null>(null)
    const [isClearingHistory, setIsClearingHistory] = useState(false)
    const [feedbackPrompt, setFeedbackPrompt] = useState<{ sessionId: string } | null>(null)
    const [feedbackScore, setFeedbackScore] = useState<number | null>(null)
    const [feedbackComment, setFeedbackComment] = useState('')
    const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false)
    const [emotionReport, setEmotionReport] = useState<AuraEmotionReportPreview | null>(null)
    const [isPurchasingReport, setIsPurchasingReport] = useState(false)
    const [cityAdcode, setCityAdcode] = useState<string | null>(() => readCachedCityAdcode())
    const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
    const [markedWeirdMessageIds, setMarkedWeirdMessageIds] = useState<Set<string>>(
        () => new Set(),
    )
    const token = useUserStore((state) => state.token)
    const getUserInfo = useUserStore((state) => state.getUserInfo)
    const loadHistoryMessages = useCallback(
        async (options?: { showError?: boolean; cancelled?: () => boolean }) => {
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
        aura.getMemoryRetention().then((response) => {
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
        }).catch(() => undefined)
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
    const clearFeedbackTimer = useCallback(() => {
        if (feedbackTimerRef.current) {
            clearTimeout(feedbackTimerRef.current)
            feedbackTimerRef.current = null
        }
    }, [])
    const scheduleFeedbackPrompt = useCallback(
        (sessionId: string) => {
            clearFeedbackTimer()
            feedbackTimerRef.current = setTimeout(() => {
                setFeedbackScore(null)
                setFeedbackComment('')
                setFeedbackPrompt({ sessionId })
                feedbackTimerRef.current = null
            }, FEEDBACK_IDLE_DELAY_MS)
        },
        [clearFeedbackTimer],
    )
    const enqueueAssistantMessage = useCallback(
        (payload: ChatStreamChunk) => {
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
        },
        [],
    )
    const finishStreamAfterDelivered = useCallback(() => {
        void assistantDeliveryQueueRef.current
            .catch(() => undefined)
            .then(() => {
                isSendingRef.current = false
                setIsStreaming(false)
                setIsAssistantTyping(false)
                lastCompletedSessionIdRef.current = currentSessionIdRef.current
                scheduleFeedbackPrompt(currentSessionIdRef.current)
                void loadHistoryMessages({ showError: false })
            })
    }, [loadHistoryMessages, scheduleFeedbackPrompt])
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

                    if (parsed.event === 'emotion' && parsed.emotion) {
                        setLatestEmotion(parsed.emotion)
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
        [enqueueAssistantMessage, finishStreamAfterDelivered, t, token],
    )
    useEffect(() => {
        return () => {
            clearFeedbackTimer()
            disconnect()
        }
    }, [clearFeedbackTimer, disconnect])
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
            toast.error('Unsupported attachment type', {
                description: 'Please upload text documents or images.',
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
        if (event.target.value.trim()) {
            clearFeedbackTimer()
            setFeedbackPrompt(null)
        }
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
        setLatestEmotion(null)
        setIsAssistantTyping(true)
        clearFeedbackTimer()
        setFeedbackPrompt(null)

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
                attachments: uploadedAttachments.map((file) => file.fileName),
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

    const handleSubmitFeedback = async () => {
        if (!feedbackPrompt || !feedbackScore || isSubmittingFeedback) {
            return
        }

        setIsSubmittingFeedback(true)

        try {
            await aura.submitConversationFeedback({
                sessionId: feedbackPrompt.sessionId,
                score: feedbackScore,
                comment: feedbackComment.trim() || undefined,
            })
            setFeedbackPrompt(null)
            setFeedbackScore(null)
            setFeedbackComment('')
            currentSessionIdRef.current = createSessionId()
        } catch {
            toast.error('这次评分没有保存成功', {
                description: t('chat.tryAgain'),
                position: 'top-center',
            })
        } finally {
            setIsSubmittingFeedback(false)
        }
    }

    const handlePurchaseReport = async () => {
        if (!emotionReport?.reportId || isPurchasingReport) {
            return
        }

        setIsPurchasingReport(true)

        try {
            const response = await aura.purchaseEmotionReport(emotionReport.reportId)
            if (response.data) {
                setEmotionReport({
                    eligible: true,
                    chatTurns: emotionReport.chatTurns,
                    roundsRemaining: 0,
                    reportId: response.data.id,
                    status: response.data.status,
                    priceCents: response.data.priceCents,
                    previewKeywords: response.data.previewKeywords,
                    previewText: response.data.previewText,
                    fullReport: response.data.fullReport,
                })
            }
        } catch {
            toast.error('报告暂时没有打开', {
                description: t('chat.tryAgain'),
                position: 'top-center',
            })
        } finally {
            setIsPurchasingReport(false)
        }
    }

    const handleMarkWeird = async (chatMessage: ChatMessage) => {
        if (markedWeirdMessageIds.has(chatMessage.id)) {
            return
        }

        const sessionId =
            chatMessage.sessionId ??
            feedbackPrompt?.sessionId ??
            lastCompletedSessionIdRef.current ??
            currentSessionIdRef.current
        const messageId =
            chatMessage.id.startsWith('local-') || chatMessage.id.startsWith('assistant-')
                ? undefined
                : chatMessage.id

        try {
            await aura.recordBehaviorEvent({
                sessionId,
                messageId,
                eventType: 'off_model',
                metadata: JSON.stringify({
                    contentPreview: chatMessage.content.slice(0, 200),
                }),
            })
            setMarkedWeirdMessageIds((current) => {
                const next = new Set(current)
                next.add(chatMessage.id)
                return next
            })
        } catch {
            toast.error('标记没有保存成功', {
                description: t('chat.tryAgain'),
                position: 'top-center',
            })
        }
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
            setLatestEmotion(null)
            setEmotionReport(null)
            setIsAssistantTyping(false)
            pendingAssistantMessageIdRef.current = null
            assistantDeliveryQueueRef.current = Promise.resolve()
            clearFeedbackTimer()
            setFeedbackPrompt(null)
            currentSessionIdRef.current = createSessionId()
            lastCompletedSessionIdRef.current = null
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

    const emotionDetail = latestEmotion ? getEmotionDetail(latestEmotion) : null
    const reportKeywords = parseJsonArray(emotionReport?.previewKeywords)
    const fullReport = parseFullReport(emotionReport?.fullReport)

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
                        emotionLabel={latestEmotion ? getEmotionLabel(latestEmotion) : null}
                    />
                </aside>

                <div className="relative flex min-h-0 flex-col overflow-hidden">
                <div
                    ref={messagesRef}
                    className="aura-scrollbar min-h-0 flex-1 overflow-y-auto px-4 pt-5 pb-56 sm:px-6 lg:px-8"
                >
                    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
                        {messages.map((chatMessage) => {
                            const isUser = chatMessage.role === 'user'

                            return (
                                <div
                                    key={chatMessage.id}
                                    className={cn(
                                        'group/message flex w-full',
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
                                                aria-label={isAssistantTyping ? 'Aura 正在输入' : undefined}
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
                                                    const AttachmentIcon = getAttachmentIcon(attachment)

                                                    return (
                                                        <span
                                                            key={attachment}
                                                            className={cn(
                                                                'inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-xs',
                                                                isUser
                                                                    ? 'bg-[#201733]/10'
                                                                    : 'bg-[var(--aura-surface-strong)]',
                                                            )}
                                                        >
                                                            <AttachmentIcon className="h-3.5 w-3.5 shrink-0" />
                                                            <span className="truncate">
                                                                {attachment}
                                                            </span>
                                                        </span>
                                                    )
                                                })}
                                            </div>
                                        ) : null}
                                    </div>
                                    {!isUser && chatMessage.content ? (
                                        <button
                                            type="button"
                                            disabled={markedWeirdMessageIds.has(chatMessage.id)}
                                            className={cn(
                                                'mx-1 self-center rounded-full px-2 py-1 text-[11px] text-[var(--aura-text-muted)] opacity-0 transition hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-text)] group-hover/message:opacity-100 focus-visible:opacity-100 disabled:opacity-45',
                                                markedWeirdMessageIds.has(chatMessage.id) && 'opacity-45',
                                            )}
                                            onClick={() => handleMarkWeird(chatMessage)}
                                        >
                                            😶 有点奇怪
                                        </button>
                                    ) : null}
                                    {chatMessage.content ? (
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon-xs"
                                            className={cn(
                                                'mx-1 self-center rounded-full text-[var(--aura-text-muted)] opacity-0 transition-opacity hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)] group-hover/message:opacity-100 focus-visible:opacity-100',
                                                isUser ? 'order-first' : 'order-last',
                                                copiedMessageId === chatMessage.id && 'opacity-100',
                                            )}
                                            aria-label="复制消息"
                                            title={copiedMessageId === chatMessage.id ? '已复制' : '复制消息'}
                                            onClick={() => handleCopyMessage(chatMessage)}
                                        >
                                            <Copy className="h-3.5 w-3.5" />
                                        </Button>
                                    ) : null}
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon-xs"
                                        disabled={isStreaming || deletingMessageId === chatMessage.id}
                                        className={cn(
                                            'mx-1 self-center rounded-full text-[var(--aura-text-muted)] opacity-0 transition-opacity hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)] group-hover/message:opacity-100 focus-visible:opacity-100',
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

                <div className="absolute inset-x-0 bottom-0 flex justify-center border-t border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-bg)_88%,transparent)] px-4 py-4 backdrop-blur-xl sm:px-6 lg:px-8">
                    <div className="w-full max-w-3xl rounded-[1.25rem] border border-[var(--aura-border)] bg-[var(--aura-surface)] p-3 shadow-[0_22px_64px_-46px_var(--aura-glow)]">
                        {selectedFiles.length > 0 ? (
                            <div className="mb-3 flex flex-wrap gap-2">
                                {selectedFiles.map((file) => {
                                    const AttachmentIcon = getAttachmentIcon(file.name)

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
                                    accept="image/*,.txt,.md,.markdown,.csv,.json,.pdf,.doc,.docx"
                                    multiple
                                    className="hidden"
                                    onChange={handleFileChange}
                                />
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                                    aria-label="Upload text or image"
                                    title="Upload text or image"
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
                                    disabled={isStreaming || isClearingHistory || messages.length === 0}
                                    className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                                    aria-label={t('chat.clearHistory')}
                                    title={t('chat.clearHistory')}
                                    onClick={handleClearHistory}
                                >
                                    <Trash2 className="h-4 w-4" />
                                </Button>
                                {latestEmotion ? (
                                    <div
                                        className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full bg-[var(--aura-surface-strong)] px-3 py-1.5 text-xs text-[var(--aura-text-muted)] sm:max-w-[18rem]"
                                        title={getEmotionLabel(latestEmotion)}
                                    >
                                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--aura-primary)]" />
                                        <span className="shrink-0 text-[var(--aura-text-soft)]">
                                            {t('chat.emotion')}
                                        </span>
                                        <span className="min-w-0 truncate">
                                            {getEmotionLabel(latestEmotion)}
                                        </span>
                                        {emotionDetail ? (
                                            <span className="shrink-0 text-[var(--aura-text-muted)]/75">
                                                {emotionDetail}
                                            </span>
                                        ) : null}
                                    </div>
                                ) : null}
                            </div>

                            <Button
                                type="button"
                                size="icon-lg"
                                disabled={
                                    isStreaming || (!message.trim() && selectedFiles.length === 0)
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
