import { Global, Module } from '@nestjs/common'
import { JwtUtil } from './jwt.util'

@Global()
@Module({
    providers: [JwtUtil],
    exports: [JwtUtil],
})
export class AuthModule {}
