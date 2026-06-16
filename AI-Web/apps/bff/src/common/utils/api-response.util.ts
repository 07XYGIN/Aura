import type { ApiResponse } from '../interfaces/api-response.interface'

export class ApiResponseUtil {
    static ok(): ApiResponse {
        return {
            code: 200,
            message: '操作成功',
        }
    }

    static success<T>(data: T): ApiResponse<T> {
        return {
            code: 200,
            message: '操作成功',
            data,
        }
    }

    static loginSuccess(token: string): ApiResponse {
        return {
            code: 200,
            message: '操作成功',
            token,
        }
    }

    static error(code: number, message: string): ApiResponse {
        return {
            code,
            message,
        }
    }
}
