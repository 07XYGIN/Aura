'use client'

import { useCallback, useEffect, useId, useMemo, useRef, useState, type ChangeEvent } from 'react'
import { ImagePlus, Mic, Paperclip, SendHorizontal, Square, Trash2 } from 'lucide-react'
import { AruaAppShell } from '@/components/arua/app-shell'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { UseSse } from '@ai-web/utils/main'
import { cn } from '@/lib/utils'
import type { BrowserSpeechRecognition, ChatMessage } from '@/types/arua'
import { toast } from 'sonner'
import { useUserStore } from '@/store/user'
import { useI18n } from '@/lib/i18n'
import { aura, type AuraHistoryMessage } from '@/apis/aura'

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
        role,
        content: item.content,
    }
}

const buildChatSseUrl = () => {
    const baseUrl = process.env.NEXT_PUBLIC_BFF_URL ?? process.env.NEXT_PUBLIC_API_URL ?? ''

    return `${baseUrl.replace(/\/+$/, '')}/api/chat/sse`
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
    const { t } = useI18n()
    const inputId = useId()
    const fileInputRef = useRef<HTMLInputElement>(null)
    const messagesRef = useRef<HTMLDivElement>(null)
    const recognitionRef = useRef<BrowserSpeechRecognition | null>(null)
    const isSendingRef = useRef(false)
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [message, setMessage] = useState('')
    const [isListening, setIsListening] = useState(false)
    const [isStreaming, setIsStreaming] = useState(false)
    const [selectedFiles, setSelectedFiles] = useState<File[]>([])
    const [latestEmotion, setLatestEmotion] = useState<EmotionPayload | null>(null)
    const [deletingMessageId, setDeletingMessageId] = useState<string | null>(null)
    const [isClearingHistory, setIsClearingHistory] = useState(false)
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
    const { connect, disconnect } = useMemo(
        () =>
            UseSse(buildChatSseUrl(), {
                headers: token ? { Authorization: `Bearer ${token}` } : undefined,
                onMessage: (data) => {
                    if (data === '[DONE]') {
                        isSendingRef.current = false
                        setIsStreaming(false)
                        void loadHistoryMessages({ showError: false })
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
                            }
                        }),
                    )
                },
                onError: () => {
                    isSendingRef.current = false
                    setIsStreaming(false)
                    toast.error(t('chat.streamFailed'), {
                        description: t('chat.tryAgain'),
                        position: 'top-center',
                    })
                },
                onClose: () => {
                    isSendingRef.current = false
                    setIsStreaming(false)
                },
            }),
        [loadHistoryMessages, t, token],
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
        setSelectedFiles(Array.from(event.target.files ?? []))
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
        recognition.lang = 'zh-CN'
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

    const handleSubmit = () => {
        if (isSendingRef.current || isStreaming) {
            return
        }

        const trimmedMessage = message.trim()

        if (!trimmedMessage && selectedFiles.length === 0) {
            return
        }

        const now = Date.now()
        const clientMessageId = `client-${now}-${Math.random().toString(36).slice(2, 10)}`
        const assistantMessageId = `assistant-${now}`
        isSendingRef.current = true
        setIsStreaming(true)
        setLatestEmotion(null)

        setMessages((currentMessages) => [
            ...currentMessages,
            {
                id: `local-${now}`,
                role: 'user',
                content: trimmedMessage,
                attachments: selectedFiles.map((file) => file.name),
            },
            {
                id: assistantMessageId,
                role: 'assistant',
                content: '',
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
                message: trimmedMessage,
            }),
        })
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

    return (
        <AruaAppShell
            active="chat"
            hideHeader
            showDefaultAction={false}
            title={null}
            contentClassName="relative min-h-0 flex-1 overflow-hidden p-0 sm:p-0 lg:p-0"
        >
            <section className="absolute inset-0 flex min-h-0 w-full flex-col overflow-hidden bg-[color-mix(in_srgb,var(--aura-surface-solid)_72%,transparent)]">
                <div
                    ref={messagesRef}
                    className="aura-scrollbar min-h-0 flex-1 overflow-y-auto px-4 pt-6 pb-52 sm:px-8 lg:px-10"
                >
                    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
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
                                            'max-w-[82%] rounded-3xl px-4 py-3 text-sm leading-7 shadow-[0_18px_42px_-34px_var(--aura-glow)] sm:max-w-[72%]',
                                            isUser
                                                ? 'rounded-br-lg bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-[#201733]'
                                                : 'rounded-bl-lg border border-[var(--aura-border)] bg-[var(--aura-surface)] text-[var(--aura-text)]',
                                        )}
                                    >
                                        {chatMessage.content ? (
                                            <p className="break-words whitespace-pre-wrap">
                                                {chatMessage.content}
                                            </p>
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
                                                {chatMessage.attachments.map((attachment) => (
                                                    <span
                                                        key={attachment}
                                                        className={cn(
                                                            'inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-xs',
                                                            isUser
                                                                ? 'bg-[#201733]/10'
                                                                : 'bg-[var(--aura-surface-strong)]',
                                                        )}
                                                    >
                                                        <ImagePlus className="h-3.5 w-3.5 shrink-0" />
                                                        <span className="truncate">
                                                            {attachment}
                                                        </span>
                                                    </span>
                                                ))}
                                            </div>
                                        ) : null}
                                    </div>
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

                <div className="absolute inset-x-0 bottom-0 flex justify-center border-t border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-bg)_86%,transparent)] px-4 py-4 backdrop-blur-xl sm:px-8 lg:px-10">
                    <div className="w-full max-w-4xl rounded-2xl border border-[var(--aura-border)] bg-[var(--aura-surface)] p-3">
                        {selectedFiles.length > 0 ? (
                            <div className="mb-3 flex flex-wrap gap-2">
                                {selectedFiles.map((file) => (
                                    <div
                                        key={`${file.name}-${file.lastModified}`}
                                        className="inline-flex max-w-full items-center gap-2 rounded-full bg-[var(--aura-surface-strong)] px-3 py-1.5 text-xs text-[var(--aura-text-muted)]"
                                    >
                                        <ImagePlus className="h-3.5 w-3.5 shrink-0 text-[var(--aura-primary)]" />
                                        <span className="truncate">{file.name}</span>
                                    </div>
                                ))}
                            </div>
                        ) : null}

                        <Textarea
                            rows={3}
                            value={message}
                            onChange={(event) => setMessage(event.target.value)}
                            placeholder={t('chat.placeholder')}
                            className="aura-scrollbar min-h-24 resize-none border-0 bg-transparent px-1 py-1 text-sm leading-7 text-[var(--aura-text)] shadow-none ring-0 focus-visible:border-0 focus-visible:ring-0"
                        />

                        <div className="mt-3 flex items-end justify-between gap-3">
                            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                                <input
                                    id={inputId}
                                    ref={fileInputRef}
                                    type="file"
                                    accept="image/*"
                                    multiple
                                    className="hidden"
                                    onChange={handleFileChange}
                                />
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                                    aria-label={t('chat.uploadImage')}
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
            </section>
        </AruaAppShell>
    )
}
