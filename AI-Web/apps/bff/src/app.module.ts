import { Module } from '@nestjs/common'
import { APP_FILTER, APP_GUARD, APP_INTERCEPTOR } from '@nestjs/core'
import { AuraModule } from './aura/aura.module'
import { AuthGuard } from './auth/auth.guard'
import { AuthModule } from './auth/auth.module'
import { ChatModule } from './chat/chat.module'
import { GlobalExceptionFilter } from './common/filters/global-exception.filter'
import { RequestLoggingInterceptor } from './common/interceptors/request-logging.interceptor'
import { ResponseInterceptor } from './common/interceptors/response.interceptor'
import { AppConfigModule } from './config/config.module'
import { LocationModule } from './location/location.module'
import { RedisModule } from './redis/redis.module'
import { UserController } from './user/user.controller'
import { UserService } from './user/user.service'

@Module({
    imports: [AppConfigModule, RedisModule, AuthModule, ChatModule, AuraModule, LocationModule],
    controllers: [UserController],
    providers: [
        UserService,
        {
            provide: APP_GUARD,
            useClass: AuthGuard,
        },
        {
            provide: APP_INTERCEPTOR,
            useClass: ResponseInterceptor,
        },
        {
            provide: APP_INTERCEPTOR,
            useClass: RequestLoggingInterceptor,
        },
        {
            provide: APP_FILTER,
            useClass: GlobalExceptionFilter,
        },
    ],
})
export class AppModule {}
