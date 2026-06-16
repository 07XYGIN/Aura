import { HttpException, Injectable } from '@nestjs/common'
import axios, { type Method } from 'axios'
import type { ApiResponse } from '../common/interfaces/api-response.interface'
import { AppConfigService } from '../config/app-config.service'

type ProxyOptions = {
    authorization?: string
    body?: unknown
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

    private throwProxyError(error: unknown): never {
        if (axios.isAxiosError<unknown>(error)) {
            const statusCode = error.response?.status ?? 502
            const responseData = error.response?.data

            if (this.isApiResponse(responseData)) {
                throw new HttpException(responseData.message, statusCode)
            }

            throw new HttpException(error.message || 'Java service request failed', statusCode)
        }

        throw new HttpException('Java service request failed', 502)
    }

    private isApiResponse(value: unknown): value is ApiResponse {
        return typeof value === 'object' && value !== null && 'code' in value && 'message' in value
    }
}
