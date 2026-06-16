import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from '@nestjs/common'
import { Reflector } from '@nestjs/core'
import type { Request } from 'express'
import { IS_PUBLIC_KEY } from '../common/decorators/public.decorator'
import { RedisUtil } from '../redis/redis.util'
import { JwtUtil } from './jwt.util'
import type { AuthUser } from './interfaces/auth-user.interface'

type RequestWithUser = Request & { user?: AuthUser }

@Injectable()
export class AuthGuard implements CanActivate {
    constructor(
        private readonly reflector: Reflector,
        private readonly jwtUtil: JwtUtil,
        private readonly redisUtil: RedisUtil,
    ) {}

    async canActivate(context: ExecutionContext): Promise<boolean> {
        const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
            context.getHandler(),
            context.getClass(),
        ])

        if (isPublic) {
            return true
        }

        const request = context.switchToHttp().getRequest<RequestWithUser>()

        if (request.method === 'OPTIONS') {
            return true
        }

        const token = this.extractBearerToken(request)
        const userId = this.resolveUserId(token)
        const redisToken = await this.redisUtil.get(`token:${userId}`)

        if (!redisToken || redisToken !== token) {
            throw new UnauthorizedException('token已失效，请重新登录')
        }

        request.user = {
            userId,
            token,
        }

        return true
    }

    private extractBearerToken(request: Request): string {
        const authHeader = request.headers.authorization

        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            throw new UnauthorizedException('未携带token')
        }

        return authHeader.slice('Bearer '.length)
    }

    private resolveUserId(token: string): string {
        if (!this.jwtUtil.validateToken(token)) {
            throw new UnauthorizedException('token已过期或非法')
        }

        return this.jwtUtil.getSubjectFromToken(token)
    }
}
