import { ArgumentsHost, Catch, ExceptionFilter, HttpException } from '@nestjs/common'
import type { Response } from 'express'
import { ApiResponseUtil } from '../utils/api-response.util'

@Catch()
export class GlobalExceptionFilter implements ExceptionFilter {
    catch(exception: unknown, host: ArgumentsHost) {
        const ctx = host.switchToHttp()
        const response = ctx.getResponse<Response>()
        const statusCode = exception instanceof HttpException ? exception.getStatus() : 500

        response
            .status(statusCode)
            .json(ApiResponseUtil.error(statusCode, this.resolveMessage(exception, statusCode)))
    }

    private resolveMessage(exception: unknown, statusCode: number): string {
        if (!(exception instanceof HttpException)) {
            return '服务器内部错误'
        }

        const errorResponse = exception.getResponse()

        if (typeof errorResponse === 'string') {
            return errorResponse
        }

        if (typeof errorResponse === 'object' && errorResponse !== null) {
            const message = (errorResponse as { message?: unknown }).message

            if (Array.isArray(message)) {
                const [firstMessage] = message as unknown[]
                return typeof firstMessage === 'string' ? firstMessage : '参数校验失败'
            }

            if (typeof message === 'string') {
                return message
            }
        }

        if (statusCode === 422) {
            return '参数校验失败'
        }

        return exception.message || '请求处理失败'
    }
}
