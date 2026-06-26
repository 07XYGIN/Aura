import { BadRequestException, HttpException, Injectable, Logger } from '@nestjs/common'
import axios from 'axios'
import type { Response } from 'express'
import type { Readable } from 'stream'
import { AppConfigService } from '../config/app-config.service'

type ChatSsePayload = {
    message?: unknown
    clientMessageId?: unknown
    sessionId?: unknown
    attachmentIds?: unknown
    cityAdcode?: unknown
    userId?: unknown
    token?: unknown
}

type ApiResponse<T = unknown> = {
    code: number
    message?: string
    data?: T
}

type PythonApiResponse<T = unknown> = {
    code: number
    msg?: string
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
    memory_scope?: 'short' | 'mid' | 'long'
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
    memory_reference?: {
        query?: string
        source?: string
        [key: string]: unknown
    }
    relationship_delta?: RelationshipDeltaPayload
}

type ChatAttachment = {
    id: string
    fileName: string
    contentType?: string
    size?: number
    summary?: string
}

type PersistedTurn = {
    userId: string
    message: string
    sessionId?: string
    clientMessageId?: string
    assistantContent: string
    emotion?: EmotionPayload
    memoryCandidate?: MemoryCandidatePayload
    memoryReferenced?: boolean
    memoryReference?: StreamEvent['memory_reference']
    relationshipDelta?: RelationshipDeltaPayload
    attachments?: ChatAttachment[]
    startedAt: number
}

@Injectable()
export class ChatService {
    private readonly logger = new Logger(ChatService.name)
    private readonly activeClientMessages = new Map<string, number>()
    private readonly clientMessageTtlMs = 2 * 60 * 1000

    constructor(private readonly config: AppConfigService) {}

    async uploadAttachments(payload: unknown, userId: string): Promise<ApiResponse<{ items: ChatAttachment[] }>> {
        const files = this.parseUploadFiles(payload)
        if (files.length === 0) {
            throw new BadRequestException('files are required')
        }

        return this.forwardAi<{ items: ChatAttachment[] }>(
            'post',
            '/api/attachments',
            {
                userId,
                files,
            },
        )
    }

    async streamSse(payload: ChatSsePayload, response: Response): Promise<void> {
        if (typeof payload.userId !== 'string' || payload.userId.trim().length === 0) {
            throw new BadRequestException('userId is required')
        }

        if (typeof payload.token !== 'string' || payload.token.trim().length === 0) {
            throw new BadRequestException('token is required')
        }

        const message = typeof payload.message === 'string' ? payload.message.trim() : ''
        const userId = payload.userId
        const attachmentIds = this.parseAttachmentIds(payload.attachmentIds)
        const cityAdcode = this.parseCityAdcode(payload.cityAdcode)
        const attachments = attachmentIds.map((id) => ({
            id,
            fileName: id,
        }))

        if (!message && attachmentIds.length === 0) {
            throw new BadRequestException('message or attachmentIds is required')
        }

        const clientMessageId =
            typeof payload.clientMessageId === 'string' ? payload.clientMessageId.trim() : ''
        const sessionId =
            typeof payload.sessionId === 'string' && payload.sessionId.trim().length > 0
                ? payload.sessionId.trim()
                : undefined
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

        const startedAt = Date.now()
        this.logger.log(
            `SSE chat start userId=${userId} sessionId=${sessionId ?? 'auto'} clientMessageId=${clientMessageId || 'none'}`,
        )

        const upstreamResponse = await axios
            .post<Readable>(
                `${this.config.aiServiceUrl}/api/send/sse/`,
                { message, userId, clientMessageId, attachmentIds, cityAdcode },
                {
                    responseType: 'stream',
                    headers: {
                        Accept: 'text/event-stream',
                        'Content-Type': 'application/json',
                    },
                },
            )
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
            let memoryReferenced = false
            let memoryReference: StreamEvent['memory_reference'] | undefined
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
                void this.persistTurnToAura({
                    userId,
                    message,
                    sessionId,
                    clientMessageId,
                    assistantContent,
                    emotion: latestEmotion,
                    memoryCandidate,
                    memoryReferenced,
                    memoryReference,
                    relationshipDelta,
                    attachments,
                    startedAt,
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
                        (event.event === 'memory_reference' || event.type === 'memory_reference') &&
                        event.memory_reference
                    ) {
                        memoryReferenced = true
                        memoryReference = event.memory_reference
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
                    void this.persistTurnToAura({
                        userId,
                        message,
                        sessionId,
                        clientMessageId,
                        assistantContent,
                        emotion: latestEmotion,
                        memoryCandidate,
                        memoryReferenced,
                        memoryReference,
                        relationshipDelta,
                        attachments,
                        startedAt,
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

    private async createAuraSession(
        userId: string,
        message: string,
        sessionId?: string,
    ): Promise<ConversationSession> {
        const response = await this.forwardAi<ConversationSession>(
            'post',
            '/api/aura/sessions',
            {
                userId,
                id: sessionId,
                channel: 'chat',
                title: message.slice(0, 40) || '附件消息',
                status: 'active',
            },
        )

        if (!response.data?.id) {
            throw new HttpException('AI service did not return session id', 502)
        }

        this.logger.log(`Prepared conversation session userId=${userId} sessionId=${response.data.id}`)
        return response.data
    }

    private async persistTurnToAura(input: PersistedTurn): Promise<void> {
        if (!input.assistantContent.trim()) {
            this.logger.warn(`Skip Aura persistence because assistant content is empty userId=${input.userId}`)
            return
        }

        try {
            const session = await this.createAuraSession(
                input.userId,
                input.message,
                input.sessionId,
            )
            await this.persistUserMessage(input.userId, session.id, input.message, input.attachments)
            const assistantMessageId = await this.persistAssistantTurn({
                userId: input.userId,
                sessionId: session.id,
                content: input.assistantContent,
                emotion: input.emotion,
                memoryCandidate: input.memoryCandidate,
                relationshipDelta: input.relationshipDelta,
            })
            await this.recordBehaviorEvent(input.userId, {
                sessionId: session.id,
                messageId: assistantMessageId,
                eventType: 'chat_turn',
                metadata: JSON.stringify({
                    clientMessageId: input.clientMessageId || null,
                    userMessageLength: input.message.length,
                    assistantMessageLength: input.assistantContent.length,
                    durationMs: Math.max(0, Date.now() - input.startedAt),
                    deepNight: this.isDeepNight(new Date()),
                    memoryReferenced: input.memoryReferenced ?? false,
                }),
            })
            if (input.memoryReferenced) {
                await this.recordBehaviorEvent(input.userId, {
                    sessionId: session.id,
                    messageId: assistantMessageId,
                    eventType: 'memory_reference',
                    metadata: JSON.stringify({
                        source: input.memoryReference?.source ?? 'search_memory_tool',
                        query: input.memoryReference?.query ?? null,
                    }),
                })
            }
            this.logger.log(`Persisted chat turn to Aura Python userId=${input.userId} sessionId=${session.id}`)
        } catch (error) {
            this.logger.error(`Aura Python persistence failed userId=${input.userId}`, this.errorStack(error))
        }
    }

    private async persistUserMessage(
        userId: string,
        sessionId: string,
        content: string,
        attachments?: ChatAttachment[],
    ): Promise<void> {
        try {
            await this.forwardAi<ChatMessageResponse>(
                'post',
                `/api/aura/sessions/${encodeURIComponent(sessionId)}/messages`,
                {
                    userId,
                    senderType: 'user',
                    content: content || '（用户发送了附件）',
                    contentType: attachments?.length ? 'text_with_attachment' : 'text',
                    metadata: JSON.stringify({
                        attachments: attachments ?? [],
                    }),
                },
            )
            this.logger.log(`Persisted user message sessionId=${sessionId}`)
        } catch (error) {
            this.logger.error(`Persist user message failed sessionId=${sessionId}`, this.errorStack(error))
        }
    }

    private async persistAssistantTurn(input: {
        userId: string
        sessionId: string
        content: string
        emotion?: EmotionPayload
        memoryCandidate?: MemoryCandidatePayload
        relationshipDelta?: RelationshipDeltaPayload
    }): Promise<string | undefined> {
        if (!input.content.trim()) {
            this.logger.warn(`Skip assistant persistence because content is empty sessionId=${input.sessionId}`)
            return undefined
        }

        try {
            const messageResponse = await this.forwardAi<ChatMessageResponse>(
                'post',
                `/api/aura/sessions/${encodeURIComponent(input.sessionId)}/messages`,
                {
                    userId: input.userId,
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
            )

            const messageId = messageResponse.data?.message?.id
            this.logger.log(
                `Persisted assistant message sessionId=${input.sessionId} messageId=${messageId ?? 'unknown'}`,
            )

            if (input.memoryCandidate?.save && input.memoryCandidate.content) {
                await this.forwardAi(
                    'post',
                    '/api/aura/memories',
                    {
                        userId: input.userId,
                        sourceSessionId: input.sessionId,
                        sourceMessageId: messageId,
                        memoryType: input.memoryCandidate.memory_scope === 'mid' ? 'mid_term' : 'long_term',
                        title: input.memoryCandidate.title ?? '对话记忆',
                        content: input.memoryCandidate.content,
                        confidence: input.memoryCandidate.confidence,
                        tags: JSON.stringify(input.memoryCandidate.signals ?? []),
                        metadata: JSON.stringify({
                            reason: input.memoryCandidate.reason ?? null,
                            memoryScope: input.memoryCandidate.memory_scope ?? 'long',
                        }),
                    },
                )
                this.logger.log(`Persisted memory candidate sessionId=${input.sessionId}`)
            }

            if (input.relationshipDelta) {
                await this.forwardAi(
                    'post',
                    '/api/aura/relationship/events',
                    {
                        userId: input.userId,
                        eventType: 'chat_turn',
                        title: input.relationshipDelta.label ?? '对话互动',
                        description: input.relationshipDelta.reason ?? 'AI 对话产生关系变化',
                        deltaIntimacy: input.relationshipDelta.intimacy_delta ?? 0,
                        deltaTrust: input.relationshipDelta.trust_delta ?? 0,
                        metadata: JSON.stringify(input.relationshipDelta),
                    },
                )
                this.logger.log(`Persisted relationship event sessionId=${input.sessionId}`)
            }

            return messageId
        } catch (error) {
            this.logger.error(`Persist assistant turn failed sessionId=${input.sessionId}`, this.errorStack(error))
            return undefined
        }
    }

    private async recordBehaviorEvent(
        userId: string,
        body: {
            sessionId?: string
            messageId?: string
            eventType: string
            metadata?: string
        },
    ): Promise<void> {
        try {
            await this.forwardAi(
                'post',
                '/api/aura/behavior-events',
                {
                    ...body,
                    userId,
                },
            )
        } catch (error) {
            this.logger.warn(`Persist behavior event failed eventType=${body.eventType}: ${this.errorMessage(error)}`)
        }
    }

    private parseAttachmentIds(value: unknown): string[] {
        if (!Array.isArray(value)) {
            return []
        }

        return value
            .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
            .map((item) => item.trim())
            .slice(0, 4)
    }

    private parseCityAdcode(value: unknown): string | undefined {
        if (typeof value !== 'string') {
            return undefined
        }

        const cityAdcode = value.trim()
        return /^\d{6}$/.test(cityAdcode) ? cityAdcode : undefined
    }

    private parseUploadFiles(payload: unknown): Array<{
        fileName: string
        contentType: string
        size: number
        dataBase64: string
    }> {
        const files = this.isPlainObject(payload) && Array.isArray(payload.files) ? payload.files : []

        return files
            .map((file) => {
                if (!this.isPlainObject(file)) {
                    throw new BadRequestException('invalid file payload')
                }

                const fileName = typeof file.fileName === 'string' ? file.fileName.trim() : ''
                const contentType = typeof file.contentType === 'string' ? file.contentType.trim() : ''
                const dataBase64 = typeof file.dataBase64 === 'string' ? file.dataBase64 : ''
                const size = typeof file.size === 'number' ? file.size : Number(file.size)

                if (!fileName || !contentType || !dataBase64 || !Number.isFinite(size)) {
                    throw new BadRequestException('invalid file payload')
                }

                return {
                    fileName,
                    contentType,
                    size,
                    dataBase64,
                }
            })
            .slice(0, 4)
    }

    private isPlainObject(value: unknown): value is Record<string, unknown> {
        return typeof value === 'object' && value !== null && !Array.isArray(value)
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

    private isDeepNight(date: Date): boolean {
        const hourText = new Intl.DateTimeFormat('en-US', {
            hour: 'numeric',
            hour12: false,
            timeZone: 'Asia/Shanghai',
        }).format(date)
        const hour = Number(hourText)
        return hour >= 22 || hour < 2
    }

    private async forwardAi<T>(
        method: 'get' | 'post' | 'put' | 'delete',
        path: string,
        data: unknown,
    ): Promise<ApiResponse<T>> {
        const response = await axios.request<PythonApiResponse<T>>({
            method,
            url: `${this.config.aiServiceUrl}${path}`,
            data,
        })

        if (response.data.code < 200 || response.data.code >= 300) {
            throw new HttpException(
                response.data.msg ?? response.data.message ?? 'AI service request failed',
                response.data.code,
            )
        }

        return {
            code: response.data.code,
            message: response.data.msg ?? response.data.message,
            data: response.data.data,
        }
    }

    private throwProxyError(error: unknown): never {
        if (axios.isAxiosError<unknown>(error)) {
            const responseData = error.response?.data
            if (this.isPythonApiResponse(responseData)) {
                throw new HttpException(
                    responseData.msg ?? responseData.message ?? 'AI service request failed',
                    error.response?.status ?? 502,
                )
            }
            if (this.hasDetailMessage(responseData)) {
                throw new HttpException(responseData.detail, error.response?.status ?? 502)
            }

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

    private errorMessage(error: unknown): string {
        return error instanceof Error ? error.message : String(error)
    }

    private isPythonApiResponse(value: unknown): value is PythonApiResponse {
        return typeof value === 'object' && value !== null && 'code' in value
    }

    private hasDetailMessage(value: unknown): value is { detail: string } {
        return (
            typeof value === 'object' &&
            value !== null &&
            'detail' in value &&
            typeof (value as { detail?: unknown }).detail === 'string'
        )
    }
}
