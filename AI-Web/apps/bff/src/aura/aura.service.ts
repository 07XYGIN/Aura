import { BadRequestException, HttpException, Injectable, Logger } from '@nestjs/common'
import axios, { type Method } from 'axios'
import type { ApiResponse } from '../common/interfaces/api-response.interface'
import { ApiResponseUtil } from '../common/utils/api-response.util'
import { AppConfigService } from '../config/app-config.service'

type ProxyOptions = {
    authorization?: string
    body?: unknown
}

type PythonApiResponse<T = unknown> = {
    code: number
    data?: T
    msg?: string
    message?: string
}

type EmotionState = {
    user_emotion: string
    aura_mood: string
    valence: number
    arousal: number
    intensity: number
    support_needed: boolean
    matched_keywords: string[]
    source: string
}

type AdminResourceParams = {
    userId?: string
    keyword?: string
    page: string
    pageSize: string
    token: string
}

@Injectable()
export class AuraService {
    private readonly logger = new Logger(AuraService.name)

    constructor(private readonly config: AppConfigService) {}

    async getInitialSetting(userId: string, token: string, sessionId?: string): Promise<ApiResponse> {
        const upstream = await this.tryForwardCore(
            'GET',
            '/api/aura/initial-setting',
            {
                authorization: this.toBearerToken(token),
            },
        )

        return (
            upstream ??
            ApiResponseUtil.success({
                userId,
                sessionId: sessionId ?? null,
                configured: false,
                setting: null,
                source: 'bff-fallback',
            })
        )
    }

    async saveInitialSetting(body: unknown, userId: string, token: string): Promise<ApiResponse> {
        return this.forwardCore('POST', '/api/aura/initial-setting', {
            authorization: this.toBearerToken(token),
            body: this.withUserId(body, userId),
        })
    }

    async getRelationshipStatus(
        userId: string,
        token: string,
        message?: string,
    ): Promise<ApiResponse> {
        const upstream = await this.tryForwardCore(
            'GET',
            '/api/aura/relationship/status',
            {
                authorization: this.toBearerToken(token),
            },
        )

        return (
            upstream ??
            ApiResponseUtil.success({
                userId,
                status: 'developing',
                intimacy: 0.5,
                message: message ?? null,
                source: 'bff-fallback',
            })
        )
    }

    async getCurrentSessionMessages(userId: string): Promise<ApiResponse> {
        return this.forwardAi('GET', `/api/history/${encodeURIComponent(userId)}`)
    }

    async clearCurrentSessionMessages(userId: string, token?: string): Promise<ApiResponse> {
        const response = await this.forwardAi('DELETE', `/api/history/${encodeURIComponent(userId)}`)
        await this.tryForwardCore('DELETE', '/api/aura/sessions/current/messages', {
            authorization: token ? this.toBearerToken(token) : undefined,
        }).catch((error) => {
            this.logger.warn(`Core auxiliary chat cleanup failed userId=${userId}: ${this.errorMessage(error)}`)
        })
        return response
    }

    async deleteCurrentSessionMessage(userId: string, messageId: string): Promise<ApiResponse> {
        if (!messageId?.trim()) {
            throw new BadRequestException('messageId is required')
        }

        return this.forwardAi(
            'DELETE',
            `/api/history/${encodeURIComponent(userId)}/messages/${encodeURIComponent(messageId.trim())}`,
        )
    }

    async getMemories(userId: string, page: string, pageSize: string, scope = 'long'): Promise<ApiResponse> {
        const params = new URLSearchParams({
            userId,
            page,
            pageSize,
            scope: this.normalizeMemoryScope(scope, 'long'),
        })

        return this.forwardAi('GET', `/api/memory/list?${params.toString()}`)
    }

    async clearMemories(userId: string, token?: string, scope = 'all'): Promise<ApiResponse> {
        const params = new URLSearchParams({
            userId,
            scope: this.normalizeMemoryScope(scope, 'all'),
        })

        const response = await this.forwardAi('DELETE', `/api/memory/list?${params.toString()}`)
        await this.tryForwardCore('DELETE', '/api/aura/memories', {
            authorization: token ? this.toBearerToken(token) : undefined,
        }).catch((error) => {
            this.logger.warn(`Core auxiliary memory cleanup failed userId=${userId}: ${this.errorMessage(error)}`)
        })
        return response
    }

    async deleteMemory(userId: string, memoryId: string): Promise<ApiResponse> {
        if (!memoryId?.trim()) {
            throw new BadRequestException('memoryId is required')
        }

        const params = new URLSearchParams({
            userId,
        })

        return this.forwardAi(
            'DELETE',
            `/api/memory/${encodeURIComponent(memoryId.trim())}?${params.toString()}`,
        )
    }

    async searchMemories(userId: string, query?: string, k = '5'): Promise<ApiResponse> {
        if (!query?.trim()) {
            throw new BadRequestException('query is required')
        }

        const params = new URLSearchParams({
            userId,
            query: query.trim(),
            k,
        })

        return this.forwardAi('GET', `/api/memory/getMemory?${params.toString()}`)
    }

    async getMemoryRetention(userId: string): Promise<ApiResponse> {
        const params = new URLSearchParams({
            userId,
        })

        return this.forwardAi('GET', `/api/memory/retention?${params.toString()}`)
    }

    async getEmotion(userId: string, token: string, message?: string): Promise<ApiResponse> {
        const upstream = await this.tryForwardCore('GET', '/api/aura/emotion', {
            authorization: this.toBearerToken(token),
        })

        return upstream ?? ApiResponseUtil.success(this.deriveEmotion(message))
    }

    async submitConversationFeedback(body: unknown, userId: string): Promise<ApiResponse> {
        return this.forwardAi('POST', '/api/aura/conversation-feedback', {
            body: this.withUserId(body, userId),
        })
    }

    async recordBehaviorEvent(body: unknown, userId: string): Promise<ApiResponse> {
        return this.forwardAi('POST', '/api/aura/behavior-events', {
            body: this.withUserId(body, userId),
        })
    }

    async getEmotionReportPreview(userId: string): Promise<ApiResponse> {
        const params = new URLSearchParams({ userId })

        return this.forwardAi('GET', `/api/aura/emotion-report/preview?${params.toString()}`)
    }

    async purchaseEmotionReport(reportId: string, userId: string): Promise<ApiResponse> {
        if (!reportId?.trim()) {
            throw new BadRequestException('reportId is required')
        }

        return this.forwardAi(
            'POST',
            `/api/aura/emotion-report/${encodeURIComponent(reportId.trim())}/purchase`,
            {
                body: { userId },
            },
        )
    }

    async getAdminResourceList(resource: string, params: AdminResourceParams): Promise<ApiResponse> {
        const routeMap: Record<string, string> = {
            profiles: '/api/aura/admin/profiles',
            personas: '/api/aura/admin/personas',
            relationships: '/api/aura/admin/relationships',
            messages: '/api/aura/admin/messages',
            emotions: '/api/aura/admin/emotions',
            memories: '/api/aura/admin/memories',
        }

        const path = routeMap[resource]
        if (!path) {
            throw new BadRequestException('resource is not supported')
        }

        const query = new URLSearchParams({
            page: params.page,
            pageSize: params.pageSize,
        })

        if (params.userId) {
            query.set('userId', params.userId)
        }

        if (params.keyword) {
            query.set('keyword', params.keyword)
        }

        const upstream = await this.forwardCore('GET', `${path}?${query.toString()}`, {
            authorization: this.toBearerToken(params.token),
        })

        return upstream
    }

    private async tryForwardCore(
        method: Method,
        path: string,
        options: ProxyOptions = {},
    ): Promise<ApiResponse | undefined> {
        try {
            return await this.forwardCore(method, path, options)
        } catch (error) {
            if (error instanceof HttpException && error.getStatus() === 404) {
                return undefined
            }

            throw error
        }
    }

    private async forwardCore<T = unknown>(
        method: Method,
        path: string,
        options: ProxyOptions = {},
    ): Promise<ApiResponse<T>> {
        try {
            const response = await axios.request<ApiResponse<T>>({
                method,
                url: `${this.config.coreServiceUrl}${path}`,
                data: options.body,
                headers: this.buildHeaders(options.authorization),
            })

            return response.data
        } catch (error) {
            this.throwProxyError(error, 'Java service request failed')
        }
    }

    private async forwardAi<T = unknown>(
        method: Method,
        path: string,
        options: ProxyOptions = {},
    ): Promise<ApiResponse<T>> {
        try {
            const response = await axios.request<PythonApiResponse<T>>({
                method,
                url: `${this.config.aiServiceUrl}${path}`,
                data: options.body,
                headers: this.buildHeaders(options.authorization),
            })

            return {
                code: response.data.code,
                message: response.data.msg ?? response.data.message ?? 'success',
                data: response.data.data,
            }
        } catch (error) {
            this.throwProxyError(error, 'AI service request failed')
        }
    }

    private buildHeaders(authorization?: string): Record<string, string> | undefined {
        return authorization ? { Authorization: authorization } : undefined
    }

    private toBearerToken(token: string): string {
        return `Bearer ${token}`
    }

    private withUserId(body: unknown, userId: string): Record<string, unknown> {
        if (this.isPlainObject(body)) {
            return {
                ...body,
                userId,
            }
        }

        return {
            userId,
            value: body,
        }
    }

    private deriveEmotion(message?: string): EmotionState {
        const text = message?.trim().toLowerCase() ?? ''
        const sadKeywords = ['sad', 'anxious', 'tired', 'lonely', '难过', '焦虑', '累', '孤独']
        const happyKeywords = ['happy', 'great', '开心', '高兴', '喜欢']
        const matchedSadKeywords = sadKeywords.filter((keyword) => text.includes(keyword))
        const matchedHappyKeywords = happyKeywords.filter((keyword) => text.includes(keyword))

        if (matchedSadKeywords.length > 0) {
            return {
                user_emotion: 'distressed',
                aura_mood: 'gentle',
                valence: -0.45,
                arousal: 0.62,
                intensity: 0.68,
                support_needed: true,
                matched_keywords: matchedSadKeywords,
                source: 'bff-fallback',
            }
        }

        if (matchedHappyKeywords.length > 0) {
            return {
                user_emotion: 'happy',
                aura_mood: 'bright',
                valence: 0.72,
                arousal: 0.48,
                intensity: 0.45,
                support_needed: false,
                matched_keywords: matchedHappyKeywords,
                source: 'bff-fallback',
            }
        }

        return {
            user_emotion: 'neutral',
            aura_mood: 'warm',
            valence: 0.1,
            arousal: 0.35,
            intensity: 0.2,
            support_needed: false,
            matched_keywords: [],
            source: 'bff-fallback',
        }
    }

    private throwProxyError(error: unknown, fallbackMessage: string): never {
        if (axios.isAxiosError<unknown>(error)) {
            const statusCode = error.response?.status ?? 502
            const responseData = error.response?.data

            if (this.isApiResponse(responseData)) {
                throw new HttpException(responseData.message, statusCode)
            }

            if (this.isPythonApiResponse(responseData)) {
                throw new HttpException(responseData.msg ?? responseData.message ?? fallbackMessage, statusCode)
            }

            throw new HttpException(error.message || fallbackMessage, statusCode)
        }

        throw new HttpException(fallbackMessage, 502)
    }

    private errorMessage(error: unknown): string {
        return error instanceof Error ? error.message : String(error)
    }

    private isPlainObject(value: unknown): value is Record<string, unknown> {
        return typeof value === 'object' && value !== null && !Array.isArray(value)
    }

    private normalizeMemoryScope(scope: string, fallback: 'long' | 'mid' | 'all'): 'long' | 'mid' | 'all' {
        return scope === 'long' || scope === 'mid' || scope === 'all' ? scope : fallback
    }

    private isApiResponse(value: unknown): value is ApiResponse {
        return typeof value === 'object' && value !== null && 'code' in value && 'message' in value
    }

    private isPythonApiResponse(value: unknown): value is PythonApiResponse {
        return typeof value === 'object' && value !== null && 'code' in value && 'msg' in value
    }
}
