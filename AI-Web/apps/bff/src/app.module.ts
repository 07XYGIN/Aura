import { Module } from '@nestjs/common'
import { APP_FILTER, APP_GUARD, APP_INTERCEPTOR } from '@nestjs/core'
import { AuthGuard } from './auth/auth.guard'
import { AuthModule } from './auth/auth.module'
import { GlobalExceptionFilter } from './common/filters/global-exception.filter'
import { ResponseInterceptor } from './common/interceptors/response.interceptor'
import { AppConfigModule } from './config/config.module'
import { RedisModule } from './redis/redis.module'
import { UserController } from './user/user.controller'

@Module({
    imports: [AppConfigModule, RedisModule, AuthModule],
    controllers: [UserController],
    providers: [
        {
            provide: APP_GUARD,
            useClass: AuthGuard,
        },
        {
            provide: APP_INTERCEPTOR,
            useClass: ResponseInterceptor,
        },
        {
            provide: APP_FILTER,
            useClass: GlobalExceptionFilter,
        },
    ],
})
export class AppModule {}
