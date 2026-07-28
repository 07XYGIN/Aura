'use client'

import { useCallback, useEffect, useId, useMemo, useRef, useState, type ChangeEvent } from 'react'
import {
    Check,
    Copy,
    GitBranch,
    History,
    ImagePlus,
    Mic,
    Paperclip,
    RefreshCw,
    RotateCcw,
    SendHorizontal,
    Square,
    Star,
    ThumbsDown,
    ThumbsUp,
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
    type AuraApproval,
    type AuraEmotionReportPreview,
    type AuraHistoryMessage,
    type AuraRelationshipChapter,
    type AuraReplyFeedbackCategory,
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
    presence?: Live2DPresence
    approval?: AuraApproval
    branchId?: string
    sourceMessageId?: string
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
    const activeBranchIdRef = useRef<string | null>(null)
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [message, setMessage] = useState('')
    const [isListening, setIsListening] = useState(false)
    const [isStreaming, setIsStreaming] = useState(false)
    const [selectedFiles, setSelectedFiles] = useState<File[]>([])
    const [latestEmotion, setLatestEmotion] = useState<EmotionPayload | null>(null)
    const [latestPresence, setLatestPresence] = useState<Live2DPresence | null>(null)
    const [activeBranchId, setActiveBranchId] = useState<string | null>(null)
    const [pendingApprovals, setPendingApprovals] = useState<AuraApproval[]>([])
    const [resolvingApprovalId, setResolvingApprovalId] = useState<string | null>(null)
    const [replyFeedbackMenuMessageId, setReplyFeedbackMenuMessageId] = useState<string | null>(
        null,
    )
    const [feedbackMessageIds, setFeedbackMessageIds] = useState<Set<string>>(() => new Set())
    const [isTimelineOpen, setIsTimelineOpen] = useState(false)
    const [isTimelineLoading, setIsTimelineLoading] = useState(false)
    const [relationshipChapters, setRelationshipChapters] = useState<AuraRelationshipChapter[]>([])
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
    const token = useUserStore((state) => state.token)
    const getUserInfo = useUserStore((state) => state.getUserInfo)
    const loadHistoryMessages = useCallback(
        async (options?: {
            showError?: boolean
            cancelled?: () => boolean
            branchId?: string | null
        }) => {
            if (!token) {
                return
            }

            try {
                const branchId = options?.branchId ?? activeBranchIdRef.current
                const response = await aura.getCurrentMessages(branchId)

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

    const loadPendingApprovals = useCallback(async () => {
        if (!token) {
            return
        }

        try {
            const response = await aura.getPendingApprovals()
            setPendingApprovals(response.data?.items ?? [])
        } catch {
            // Approval controls are supplemental; normal chat remains available.
        }
    }, [token])

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
        void loadPendingApprovals()
    }, [getUserInfo, loadPendingApprovals, t, token])
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

                    if (parsed.event === 'live2d_state' && parsed.presence) {
                        setLatestPresence(parsed.presence)
                        return
                    }

                    if (parsed.event === 'approval_required' && parsed.approval) {
                        const approval = parsed.approval
                        setPendingApprovals((current) => {
                            if (current.some((item) => item.id === approval.id)) {
                                return current
                            }
                            return [...current, approval]
                        })
                        return
                    }

                    if (parsed.event === 'conversation_branch' && parsed.branchId) {
                        activeBranchIdRef.current = parsed.branchId
                        setActiveBranchId(parsed.branchId)
                        void loadHistoryMessages({ showError: false, branchId: parsed.branchId })
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
        setLatestPresence({ expression: 'thinking', motion: 'idle', intensity: 1 })
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
                branchId: activeBranchIdRef.current || undefined,
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
                branchId: activeBranchIdRef.current || undefined,
            }),
        })
    }

    const handleCreateBranch = async (chatMessage: ChatMessage) => {
        if (
            isStreaming ||
            chatMessage.id.startsWith('local-') ||
            chatMessage.id.startsWith('assistant-')
        ) {
            return
        }

        try {
            const response = await aura.createConversationBranch(
                chatMessage.id,
                activeBranchIdRef.current,
            )
            const branchId = response.data?.branchId
            if (!branchId) {
                throw new Error('Missing branch id')
            }
            activeBranchIdRef.current = branchId
            setActiveBranchId(branchId)
            setLatestPresence(null)
            await loadHistoryMessages({ showError: true, branchId })
            toast.success('已从这里创建分支', { position: 'top-center' })
        } catch {
            toast.error('创建分支失败', {
                description: t('chat.tryAgain'),
                position: 'top-center',
            })
        }
    }

    const handleResolveApproval = async (approval: AuraApproval, approved: boolean) => {
        if (resolvingApprovalId) {
            return
        }

        setResolvingApprovalId(approval.id)
        try {
            await aura.resolveApproval(approval.id, approved)
            setPendingApprovals((current) => current.filter((item) => item.id !== approval.id))
        } catch {
            toast.error('这条确认没有保存成功', {
                description: t('chat.tryAgain'),
                position: 'top-center',
            })
        } finally {
            setResolvingApprovalId(null)
        }
    }

    const handleToggleTimeline = async () => {
        const opening = !isTimelineOpen
        setIsTimelineOpen(opening)
        if (!opening) {
            return
        }

        setIsTimelineLoading(true)
        try {
            const response = await aura.getRelationshipChapters()
            setRelationshipChapters(response.data?.items ?? [])
        } catch {
            toast.error('关系时间线暂时没有打开', {
                description: t('chat.tryAgain'),
                position: 'top-center',
            })
        } finally {
            setIsTimelineLoading(false)
        }
    }

    const handleReturnToMainConversation = () => {
        activeBranchIdRef.current = null
        setActiveBranchId(null)
        setLatestPresence(null)
        void loadHistoryMessages({ showError: true, branchId: null })
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
                await aura.deleteCurrentMessage(messageId, activeBranchIdRef.current)
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
            await aura.clearCurrentMessages(activeBranchIdRef.current)
            setMessages([])
            setLatestEmotion(null)
            setLatestPresence(null)
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
                        presence={latestPresence}
                    />
                </aside>

                <div className="relative flex min-h-0 flex-col overflow-hidden">
                    <div
                        ref={messagesRef}
                        className={cn(
                            'aura-scrollbar min-h-0 flex-1 overflow-y-auto px-4 pt-5 sm:px-6 lg:px-8',
                            pendingApprovals.length > 0 ? 'pb-80' : 'pb-56',
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
                                                        disabled={isStreaming}
                                                        className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                                                        aria-label="从此处创建分支"
                                                        title="从此处创建分支"
                                                        onClick={() =>
                                                            handleCreateBranch(chatMessage)
                                                        }
                                                    >
                                                        <GitBranch className="h-3.5 w-3.5" />
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        variant="ghost"
                                                        size="icon-xs"
                                                        disabled={feedbackRecorded}
                                                        className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                                                        aria-label="这条回复合适"
                                                        title="这条回复合适"
                                                        onClick={() =>
                                                            handleReplyFeedback(
                                                                chatMessage,
                                                                'helpful',
                                                            )
                                                        }
                                                    >
                                                        {feedbackRecorded ? (
                                                            <Check className="h-3.5 w-3.5" />
                                                        ) : (
                                                            <ThumbsUp className="h-3.5 w-3.5" />
                                                        )}
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
                                                        <ThumbsDown className="h-3.5 w-3.5" />
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

                    {isTimelineOpen ? (
                        <aside className="absolute inset-y-0 right-0 z-40 flex w-full max-w-md flex-col border-l border-[var(--aura-border)] bg-[var(--aura-surface-solid)] shadow-2xl">
                            <div className="flex items-center justify-between border-b border-[var(--aura-border)] px-5 py-4">
                                <div>
                                    <p className="text-sm font-semibold text-[var(--aura-text)]">
                                        关系时间线
                                    </p>
                                    <p className="mt-1 text-xs text-[var(--aura-text-muted)]">
                                        真实形成的重要章节
                                    </p>
                                </div>
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-text)]"
                                    aria-label="关闭关系时间线"
                                    title="关闭"
                                    onClick={() => setIsTimelineOpen(false)}
                                >
                                    <X className="h-4 w-4" />
                                </Button>
                            </div>
                            <div className="aura-scrollbar min-h-0 flex-1 overflow-y-auto px-5 py-4">
                                {isTimelineLoading ? (
                                    <p className="text-sm text-[var(--aura-text-muted)]">
                                        正在整理……
                                    </p>
                                ) : relationshipChapters.length ? (
                                    <ol className="space-y-5 border-l border-[var(--aura-border)] pl-4">
                                        {relationshipChapters.map((chapter) => (
                                            <li key={chapter.id} className="relative">
                                                <span className="absolute top-1.5 -left-[21px] h-2.5 w-2.5 rounded-full bg-[var(--aura-primary)]" />
                                                <div className="flex items-baseline justify-between gap-3">
                                                    <h3 className="min-w-0 text-sm font-medium text-[var(--aura-text)]">
                                                        {chapter.title}
                                                    </h3>
                                                    <span className="shrink-0 text-[11px] text-[var(--aura-text-muted)]">
                                                        {chapter.status === 'current'
                                                            ? '进行中'
                                                            : `#${chapter.sequenceNo}`}
                                                    </span>
                                                </div>
                                                <p className="mt-1 text-sm leading-6 text-[var(--aura-text-muted)]">
                                                    {chapter.summary}
                                                </p>
                                            </li>
                                        ))}
                                    </ol>
                                ) : (
                                    <p className="text-sm leading-6 text-[var(--aura-text-muted)]">
                                        还没有需要留在时间线里的章节。
                                    </p>
                                )}
                            </div>
                        </aside>
                    ) : null}

                    <div className="absolute inset-x-0 bottom-0 flex flex-col items-center border-t border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-bg)_88%,transparent)] px-4 py-4 backdrop-blur-xl sm:px-6 lg:px-8">
                        {pendingApprovals.length > 0 ? (
                            <div className="aura-scrollbar max-h-36 w-full max-w-3xl overflow-y-auto pr-1">
                                {pendingApprovals.map((approval) => (
                                    <div
                                        key={approval.id}
                                        className="mb-3 flex w-full max-w-3xl flex-wrap items-center justify-between gap-3 border border-[var(--aura-border)] bg-[var(--aura-surface-solid)] px-3 py-2.5"
                                    >
                                        <div className="min-w-0">
                                            <p className="truncate text-sm font-medium text-[var(--aura-text)]">
                                                {approval.title}
                                            </p>
                                            <p className="truncate text-xs text-[var(--aura-text-muted)]">
                                                {approval.summary}
                                            </p>
                                        </div>
                                        <div className="flex shrink-0 items-center gap-1.5">
                                            <Button
                                                type="button"
                                                size="sm"
                                                disabled={resolvingApprovalId === approval.id}
                                                className="gap-1.5 bg-[var(--aura-primary)] text-[#201733] hover:bg-[var(--aura-primary)]/90"
                                                onClick={() =>
                                                    handleResolveApproval(approval, true)
                                                }
                                            >
                                                <Check className="h-3.5 w-3.5" />
                                                保留
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                disabled={resolvingApprovalId === approval.id}
                                                className="gap-1.5 text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)]"
                                                onClick={() =>
                                                    handleResolveApproval(approval, false)
                                                }
                                            >
                                                <X className="h-3.5 w-3.5" />
                                                不保留
                                            </Button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : null}
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
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className={cn(
                                            'rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]',
                                            isTimelineOpen &&
                                                'bg-[var(--aura-primary-soft)] text-[var(--aura-primary)]',
                                        )}
                                        aria-label="关系时间线"
                                        title="关系时间线"
                                        onClick={handleToggleTimeline}
                                    >
                                        <History className="h-4 w-4" />
                                    </Button>
                                    {activeBranchId ? (
                                        <>
                                            <span className="inline-flex h-9 items-center gap-1.5 border border-[var(--aura-border)] px-2 text-xs text-[var(--aura-text-muted)]">
                                                <GitBranch className="h-3.5 w-3.5 text-[var(--aura-primary)]" />
                                                分支
                                            </span>
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                                                aria-label="返回主会话"
                                                title="返回主会话"
                                                onClick={handleReturnToMainConversation}
                                            >
                                                <RotateCcw className="h-4 w-4" />
                                            </Button>
                                        </>
                                    ) : null}
                                    {latestEmotion ? (
                                        <div
                                            className="inline-flex max-w-full min-w-0 items-center gap-1.5 rounded-full bg-[var(--aura-surface-strong)] px-3 py-1.5 text-xs text-[var(--aura-text-muted)] sm:max-w-[18rem]"
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
