import { BadRequestException, HttpException, Injectable, Logger } from '@nestjs/common'
import axios from 'axios'
import type { Response } from 'express'
import type { Readable } from 'stream'
import { AppConfigService } from '../config/app-config.service'

type ChatSsePayload = {
    message?: unknown
    clientMessageId?: unknown
    userId?: unknown
    token?: unknown
}

type ApiResponse<T = unknown> = {
    code: number
    message?: string
    data?: T
}

type ConversationSession = {
    id: string
}

type ChatMessageResponse = {
    message?: {
        id?: string
    }
}

type EmotionPayload = {
    user_emotion?: string
    dominant_emotion?: string
    valence?: number
    arousal?: number
    intensity?: number
    confidence?: number
    reason?: string
    [key: string]: unknown
}

type MemoryCandidatePayload = {
    save?: boolean
    confidence?: number
    title?: string
    content?: string
    reason?: string
    signals?: unknown
    [key: string]: unknown
}

type RelationshipDeltaPayload = {
    intimacy_delta?: number
    trust_delta?: number
    label?: string
    reason?: string
    [key: string]: unknown
}

type StreamEvent = {
    event?: string
    type?: string
    content?: string
    emotion?: EmotionPayload
    memory_candidate?: MemoryCandidatePayload
    relationship_delta?: RelationshipDeltaPayload
}

type PersistedTurn = {
    userId: string
    message: string
    authorization: string
    assistantContent: string
    emotion?: EmotionPayload
    memoryCandidate?: MemoryCandidatePayload
    relationshipDelta?: RelationshipDeltaPayload
}

@Injectable()
export class ChatService {
    private readonly logger = new Logger(ChatService.name)
    private readonly activeClientMessages = new Map<string, number>()
    private readonly clientMessageTtlMs = 2 * 60 * 1000

    constructor(private readonly config: AppConfigService) {}

    async streamSse(payload: ChatSsePayload, response: Response): Promise<void> {
        if (typeof payload.message !== 'string' || payload.message.trim().length === 0) {
            throw new BadRequestException('message is required')
        }

        if (typeof payload.userId !== 'string' || payload.userId.trim().length === 0) {
            throw new BadRequestException('userId is required')
        }

        if (typeof payload.token !== 'string' || payload.token.trim().length === 0) {
            throw new BadRequestException('token is required')
        }

        const message = payload.message.trim()
        const userId = payload.userId
        const token = payload.token
        const clientMessageId =
            typeof payload.clientMessageId === 'string' ? payload.clientMessageId.trim() : ''
        const activeKey = clientMessageId ? `${userId}:${clientMessageId}` : ''

        if (activeKey && this.isDuplicateActiveMessage(activeKey)) {
            this.logger.warn(
                `Duplicate SSE chat ignored userId=${userId} clientMessageId=${clientMessageId}`,
            )
            response.status(409).json({
                code: 409,
                message: 'Duplicate chat request',
            })
            return
        }

        if (activeKey) {
            this.activeClientMessages.set(activeKey, Date.now())
        }

        const authHeader = `Bearer ${token}`
        this.logger.log(`SSE chat start userId=${userId} clientMessageId=${clientMessageId || 'none'}`)

        const upstreamResponse = await axios
            .post<Readable>(`${this.config.aiServiceUrl}/api/send/sse/`, { message, userId, clientMessageId }, {
                responseType: 'stream',
                headers: {
                    Accept: 'text/event-stream',
                    'Content-Type': 'application/json',
                },
            })
            .catch((error: unknown) => {
                if (activeKey) {
                    this.activeClientMessages.delete(activeKey)
                }
                this.throwProxyError(error)
            })

        response.status(200)
        response.setHeader('Content-Type', 'text/event-stream; charset=utf-8')
        response.setHeader('Cache-Control', 'no-cache, no-transform')
        response.setHeader('Connection', 'keep-alive')
        response.flushHeaders?.()

        const stream = upstreamResponse.data

        await new Promise<void>((resolve) => {
            let closed = false
            let assistantContent = ''
            let buffer = ''
            let latestEmotion: EmotionPayload | undefined
            let memoryCandidate: MemoryCandidatePayload | undefined
            let relationshipDelta: RelationshipDeltaPayload | undefined

            const close = () => {
                if (closed) {
                    return
                }

                closed = true
                if (activeKey) {
                    this.activeClientMessages.delete(activeKey)
                }
                stream.destroy()
                response.end()
                void this.persistTurnToCore({
                    userId,
                    message,
                    authorization: authHeader,
                    assistantContent,
                    emotion: latestEmotion,
                    memoryCandidate,
                    relationshipDelta,
                })
                resolve()
            }

            response.on('close', () => {
                if (!closed) {
                    stream.destroy()
                    closed = true
                    if (activeKey) {
                        this.activeClientMessages.delete(activeKey)
                    }
                    resolve()
                }
            })

            stream.on('data', (chunk: Buffer) => {
                if (closed) {
                    return
                }

                const text = chunk.toString('utf8')
                response.write(chunk)
                buffer += text

                const parts = buffer.split('\n\n')
                buffer = parts.pop() ?? ''

                for (const part of parts) {
                    const event = this.parseSseEvent(part)
                    if (!event) {
                        continue
                    }

                    if (event.content) {
                        assistantContent += event.content
                    }

                    if ((event.event === 'emotion' || event.type === 'emotion') && event.emotion) {
                        latestEmotion = event.emotion
                    }

                    if (
                        (event.event === 'memory_candidate' || event.type === 'memory_candidate') &&
                        event.memory_candidate
                    ) {
                        memoryCandidate = event.memory_candidate
                    }

                    if (
                        (event.event === 'relationship_delta' || event.type === 'relationship_delta') &&
                        event.relationship_delta
                    ) {
                        relationshipDelta = event.relationship_delta
                    }
                }

                if (chunk.includes('[DONE]')) {
                    close()
                }
            })

            stream.on('end', close)
            stream.on('error', () => {
                if (!closed) {
                    closed = true
                    if (activeKey) {
                        this.activeClientMessages.delete(activeKey)
                    }
                    response.end()
                    void this.persistTurnToCore({
                        userId,
                        message,
                        authorization: authHeader,
                        assistantContent,
                        emotion: latestEmotion,
                        memoryCandidate,
                        relationshipDelta,
                    })
                    resolve()
                }
            })
        })
    }

    private isDuplicateActiveMessage(activeKey: string): boolean {
        const now = Date.now()
        const startedAt = this.activeClientMessages.get(activeKey)

        for (const [key, timestamp] of this.activeClientMessages) {
            if (now - timestamp > this.clientMessageTtlMs) {
                this.activeClientMessages.delete(key)
            }
        }

        return typeof startedAt === 'number' && now - startedAt <= this.clientMessageTtlMs
    }

    private async createCoreSession(
        userId: string,
        authorization: string,
        message: string,
    ): Promise<ConversationSession> {
        const response = await this.forwardCore<ConversationSession>(
            'post',
            '/api/aura/sessions',
            {
                channel: 'chat',
                title: message.slice(0, 40),
                status: 'active',
            },
            authorization,
        )

        if (!response.data?.id) {
            throw new HttpException('Core service did not return session id', 502)
        }

        this.logger.log(`Created conversation session userId=${userId} sessionId=${response.data.id}`)
        return response.data
    }

    private async persistTurnToCore(input: PersistedTurn): Promise<void> {
        if (!input.assistantContent.trim()) {
            this.logger.warn(`Skip Core persistence because assistant content is empty userId=${input.userId}`)
            return
        }

        try {
            const session = await this.createCoreSession(input.userId, input.authorization, input.message)
            await this.persistUserMessage(session.id, input.message, input.authorization)
            await this.persistAssistantTurn({
                sessionId: session.id,
                content: input.assistantContent,
                emotion: input.emotion,
                memoryCandidate: input.memoryCandidate,
                relationshipDelta: input.relationshipDelta,
                authorization: input.authorization,
            })
            this.logger.log(`Persisted chat turn to Core userId=${input.userId} sessionId=${session.id}`)
        } catch (error) {
            this.logger.error(`Core persistence failed userId=${input.userId}`, this.errorStack(error))
        }
    }

    private async persistUserMessage(
        sessionId: string,
        content: string,
        authorization: string,
    ): Promise<void> {
        try {
            await this.forwardCore<ChatMessageResponse>(
                'post',
                `/api/aura/sessions/${encodeURIComponent(sessionId)}/messages`,
                {
                    senderType: 'user',
                    content,
                    contentType: 'text',
                },
                authorization,
            )
            this.logger.log(`Persisted user message sessionId=${sessionId}`)
        } catch (error) {
            this.logger.error(`Persist user message failed sessionId=${sessionId}`, this.errorStack(error))
        }
    }

    private async persistAssistantTurn(input: {
        sessionId: string
        content: string
        emotion?: EmotionPayload
        memoryCandidate?: MemoryCandidatePayload
        relationshipDelta?: RelationshipDeltaPayload
        authorization: string
    }): Promise<void> {
        if (!input.content.trim()) {
            this.logger.warn(`Skip assistant persistence because content is empty sessionId=${input.sessionId}`)
            return
        }

        try {
            const messageResponse = await this.forwardCore<ChatMessageResponse>(
                'post',
                `/api/aura/sessions/${encodeURIComponent(input.sessionId)}/messages`,
                {
                    senderType: 'assistant',
                    senderId: 'aura',
                    content: input.content,
                    contentType: 'text',
                    emotionLabel: input.emotion?.user_emotion ?? input.emotion?.dominant_emotion,
                    emotionSnapshot: input.emotion
                        ? this.toEmotionSnapshot(input.sessionId, undefined, input.emotion)
                        : undefined,
                    metadata: JSON.stringify({
                        relationshipDelta: input.relationshipDelta ?? null,
                    }),
                },
                input.authorization,
            )

            const messageId = messageResponse.data?.message?.id
            this.logger.log(
                `Persisted assistant message sessionId=${input.sessionId} messageId=${messageId ?? 'unknown'}`,
            )

            if (input.memoryCandidate?.save && input.memoryCandidate.content) {
                await this.forwardCore(
                    'post',
                    '/api/aura/memories',
                    {
                        sourceSessionId: input.sessionId,
                        sourceMessageId: messageId,
                        memoryType: 'chat_signal',
                        title: input.memoryCandidate.title ?? '对话记忆',
                        content: input.memoryCandidate.content,
                        confidence: input.memoryCandidate.confidence,
                        tags: JSON.stringify(input.memoryCandidate.signals ?? []),
                        metadata: JSON.stringify({
                            reason: input.memoryCandidate.reason ?? null,
                        }),
                    },
                    input.authorization,
                )
                this.logger.log(`Persisted memory candidate sessionId=${input.sessionId}`)
            }

            if (input.relationshipDelta) {
                await this.forwardCore(
                    'post',
                    '/api/aura/relationship/events',
                    {
                        eventType: 'chat_turn',
                        title: input.relationshipDelta.label ?? '对话互动',
                        description: input.relationshipDelta.reason ?? 'AI 对话产生关系变化',
                        deltaIntimacy: input.relationshipDelta.intimacy_delta ?? 0,
                        deltaTrust: input.relationshipDelta.trust_delta ?? 0,
                        metadata: JSON.stringify(input.relationshipDelta),
                    },
                    input.authorization,
                )
                this.logger.log(`Persisted relationship event sessionId=${input.sessionId}`)
            }
        } catch (error) {
            this.logger.error(`Persist assistant turn failed sessionId=${input.sessionId}`, this.errorStack(error))
        }
    }

    private toEmotionSnapshot(
        sessionId: string,
        messageId: string | undefined,
        emotion: EmotionPayload,
    ): Record<string, unknown> {
        return {
            sessionId,
            messageId,
            source: 'chat',
            dominantEmotion: emotion.user_emotion ?? emotion.dominant_emotion,
            valence: emotion.valence,
            arousal: emotion.arousal,
            intensity: emotion.intensity ?? emotion.confidence,
            emotionScores: JSON.stringify(emotion),
            reason: emotion.reason ?? 'AI stream emotion event',
        }
    }

    private parseSseEvent(raw: string): StreamEvent | undefined {
        const dataLines = raw
            .split(/\r?\n/)
            .filter((line) => line.startsWith('data:'))
            .map((line) => line.slice('data:'.length).trim())

        if (dataLines.length === 0) {
            return undefined
        }

        const data = dataLines.join('\n')
        if (data === '[DONE]') {
            return undefined
        }

        try {
            return JSON.parse(data) as StreamEvent
        } catch (error) {
            this.logger.warn(`Ignore invalid SSE data: ${data.slice(0, 120)}`)
            return undefined
        }
    }

    private async forwardCore<T>(
        method: 'get' | 'post' | 'put' | 'delete',
        path: string,
        data: unknown,
        authorization: string,
    ): Promise<ApiResponse<T>> {
        const response = await axios.request<ApiResponse<T>>({
            method,
            url: `${this.config.coreServiceUrl}${path}`,
            data,
            headers: {
                Authorization: authorization,
            },
        })

        if (response.data.code < 200 || response.data.code >= 300) {
            throw new HttpException(response.data.message ?? 'Core service request failed', response.data.code)
        }

        return response.data
    }

    private throwProxyError(error: unknown): never {
        if (axios.isAxiosError<unknown>(error)) {
            throw new HttpException(
                error.message || 'AI service request failed',
                error.response?.status ?? 502,
            )
        }

        throw new HttpException('AI service request failed', 502)
    }

    private errorStack(error: unknown): string | undefined {
        return error instanceof Error ? error.stack : undefined
    }
}
