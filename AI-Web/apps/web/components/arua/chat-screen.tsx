'use client'

import { useEffect, useId, useRef, useState, type ChangeEvent } from 'react'
import { ImagePlus, Mic, Paperclip, SendHorizontal, Square } from 'lucide-react'
import { AruaAppShell } from '@/components/arua/app-shell'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { UseSse } from '@ai-web/utils/main'
import { cn } from '@/lib/utils'
import type { BrowserSpeechRecognition, ChatMessage } from '@/types/arua'
import { toast } from 'sonner'

export function AruaChatScreen() {
    const inputId = useId()
    const fileInputRef = useRef<HTMLInputElement>(null)
    const messagesRef = useRef<HTMLDivElement>(null)
    const recognitionRef = useRef<BrowserSpeechRecognition | null>(null)
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [message, setMessage] = useState('')
    const [isListening, setIsListening] = useState(false)
    const [isStreaming, setIsStreaming] = useState(false)
    const [selectedFiles, setSelectedFiles] = useState<File[]>([])
    useEffect(() => {
        messagesRef.current?.scrollTo({
            top: messagesRef.current.scrollHeight,
            behavior: 'smooth',
        })
    }, [messages])
    const { connect } = UseSse('http://127.0.0.1:8000/api/send/sse/', {
        onMessage: (data) => {
            if (data === '[DONE]') {
                setIsStreaming(false)
                return
            }

            let parsed: { content?: string }

            try {
                parsed = JSON.parse(data) as { content?: string }
            } catch {
                toast.error('Message stream failed', {
                    description: 'Arua returned an invalid stream chunk.',
                    position: 'top-center',
                })
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
                    }
                }),
            )
        },
        onError: () => {
            setIsStreaming(false)
            toast.error('Message stream failed', {
                description: 'Please try sending your message again.',
                position: 'top-center',
            })
        },
    })
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
            toast.error('Voice input unavailable', {
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
            toast.error('Voice input failed', {
                description: 'Please try recording again.',
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
        const trimmedMessage = message.trim()

        if (!trimmedMessage && selectedFiles.length === 0) {
            return
        }

        const now = Date.now()
        const assistantMessageId = `assistant-${now}`
        setIsStreaming(true)

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
                message: trimmedMessage,
                userId: '1',
            }),
        })
    }

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
                                        'flex w-full',
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
                            placeholder="Message Arua..."
                            className="aura-scrollbar min-h-24 resize-none border-0 bg-transparent px-1 py-1 text-sm leading-7 text-[var(--aura-text)] shadow-none ring-0 focus-visible:border-0 focus-visible:ring-0"
                        />

                        <div className="mt-3 flex items-center justify-between gap-3">
                            <div className="flex items-center gap-2">
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
                                    aria-label="Upload image"
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
                                        isListening ? 'Stop voice input' : 'Start voice input'
                                    }
                                    onClick={handleVoiceInput}
                                >
                                    {isListening ? (
                                        <Square className="h-4 w-4" />
                                    ) : (
                                        <Mic className="h-4 w-4" />
                                    )}
                                </Button>
                            </div>

                            <Button
                                type="button"
                                size="icon-lg"
                                disabled={
                                    isStreaming || (!message.trim() && selectedFiles.length === 0)
                                }
                                className="rounded-full bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-[#201733] shadow-[0_18px_32px_-22px_var(--aura-glow)]"
                                aria-label="Send message"
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
