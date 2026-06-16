import { HttpException, Injectable } from '@nestjs/common'
import axios, { type Method } from 'axios'
import type { ApiResponse } from '../common/interfaces/api-response.interface'
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

@Injectable()
export class UserService {
    constructor(private readonly config: AppConfigService) {}

    register(body: unknown): Promise<ApiResponse> {
        return this.forward('POST', '/api/user/register', { body })
    }

    login(body: unknown): Promise<ApiResponse> {
        return this.forward('POST', '/api/user/login', { body })
    }

    logout(userId: string, authorization?: string): Promise<ApiResponse> {
        return this.forward('GET', `/api/user/logout/${encodeURIComponent(userId)}`, {
            authorization,
        })
    }

    getUserInfo(authorization?: string): Promise<ApiResponse> {
        return this.forward('GET', '/api/user/userInfo', { authorization })
    }

    async getMemoryList(userId: string, page: string, pageSize: string): Promise<ApiResponse> {
        const params = new URLSearchParams({
            userId,
            page,
            pageSize,
        })
        const response = await this.forwardAi<{
            items: unknown[]
            total: number
            page: number
            pageSize: number
            hasMore: boolean
        }>('GET', `/api/memory/list?${params.toString()}`)

        return {
            code: response.code,
            message: response.msg ?? response.message ?? 'success',
            data: response.data,
        }
    }

    updateInfo(body: unknown, authorization?: string): Promise<ApiResponse> {
        return this.forward('PUT', '/api/user/updateInfo', { authorization, body })
    }

    deleteUser(username: string, authorization?: string): Promise<ApiResponse> {
        return this.forward('DELETE', `/api/user/${encodeURIComponent(username)}`, {
            authorization,
        })
    }

    private async forward<T = unknown>(
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
            this.throwProxyError(error)
        }
    }

    private buildHeaders(authorization?: string): Record<string, string> | undefined {
        return authorization ? { Authorization: authorization } : undefined
    }

    private async forwardAi<T = unknown>(
        method: Method,
        path: string,
    ): Promise<PythonApiResponse<T>> {
        try {
            const response = await axios.request<PythonApiResponse<T>>({
                method,
                url: `${this.config.aiServiceUrl}${path}`,
            })

            return response.data
        } catch (error) {
            this.throwProxyError(error, 'AI service request failed')
        }
    }

    private throwProxyError(
        error: unknown,
        fallbackMessage = 'Java service request failed',
    ): never {
        if (axios.isAxiosError<unknown>(error)) {
            const statusCode = error.response?.status ?? 502
            const responseData = error.response?.data

            if (this.isApiResponse(responseData)) {
                throw new HttpException(responseData.message, statusCode)
            }

            if (this.isPythonApiResponse(responseData)) {
                throw new HttpException(responseData.msg ?? fallbackMessage, statusCode)
            }

            throw new HttpException(error.message || fallbackMessage, statusCode)
        }

        throw new HttpException(fallbackMessage, 502)
    }

    private isApiResponse(value: unknown): value is ApiResponse {
        return typeof value === 'object' && value !== null && 'code' in value && 'message' in value
    }

    private isPythonApiResponse(value: unknown): value is PythonApiResponse {
        return typeof value === 'object' && value !== null && 'code' in value && 'msg' in value
    }
}
