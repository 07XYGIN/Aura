import { Global, Module } from '@nestjs/common'
import { RedisUtil } from './redis.util'

@Global()
@Module({
    providers: [RedisUtil],
    exports: [RedisUtil],
})
export class RedisModule {}
