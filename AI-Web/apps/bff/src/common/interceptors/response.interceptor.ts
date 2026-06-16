import { CallHandler, ExecutionContext, Injectable, NestInterceptor } from '@nestjs/common'
import { map, Observable } from 'rxjs'
import type { ApiResponse } from '../interfaces/api-response.interface'
import { ApiResponseUtil } from '../utils/api-response.util'

@Injectable()
export class ResponseInterceptor<T> implements NestInterceptor<T, ApiResponse<T> | ApiResponse> {
    intercept(
        _context: ExecutionContext,
        next: CallHandler<T>,
    ): Observable<ApiResponse<T> | ApiResponse> {
        return next.handle().pipe(
            map((data: T | ApiResponse<T>) => {
                if (this.isApiResponse(data)) {
                    return data
                }

                if (data === undefined || data === null) {
                    return ApiResponseUtil.ok()
                }

                return ApiResponseUtil.success(data)
            }),
        )
    }

    private isApiResponse(value: T | ApiResponse<T>): value is ApiResponse<T> {
        return typeof value === 'object' && value !== null && 'code' in value && 'message' in value
    }
}
