import {
    CallHandler,
    ExecutionContext,
    Injectable,
    Logger,
    NestInterceptor,
} from '@nestjs/common'
import type { Request } from 'express'
import { Observable, tap } from 'rxjs'

@Injectable()
export class RequestLoggingInterceptor implements NestInterceptor {
    private readonly logger = new Logger(RequestLoggingInterceptor.name)

    intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
        const request = context.switchToHttp().getRequest<Request>()
        const startedAt = Date.now()

        return next.handle().pipe(
            tap({
                next: () => {
                    this.logger.log(
                        `${request.method} ${request.originalUrl} completed in ${Date.now() - startedAt}ms`,
                    )
                },
                error: (error: unknown) => {
                    const message = error instanceof Error ? error.message : 'unknown error'
                    this.logger.error(
                        `${request.method} ${request.originalUrl} failed in ${Date.now() - startedAt}ms: ${message}`,
                    )
                },
            }),
        )
    }
}
