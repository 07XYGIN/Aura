import { Injectable } from '@nestjs/common'
import { createHmac, timingSafeEqual } from 'crypto'
import { AppConfigService } from '../config/app-config.service'

interface JwtPayload {
    sub?: string
    iat?: number
    exp?: number
}

@Injectable()
export class JwtUtil {
    constructor(private readonly config: AppConfigService) {}

    generateToken(subject: string): string {
        const now = Math.floor(Date.now() / 1000)
        const header = { alg: 'HS256', typ: 'JWT' }
        const payload: JwtPayload = {
            sub: subject,
            iat: now,
            exp: now + Math.floor(this.config.jwtExpireTime / 1000),
        }
        const unsignedToken = [this.base64UrlEncode(header), this.base64UrlEncode(payload)].join(
            '.',
        )

        return `${unsignedToken}.${this.sign(unsignedToken)}`
    }

    validateToken(token: string): boolean {
        try {
            this.parseToken(token)
            return true
        } catch {
            return false
        }
    }

    getSubjectFromToken(token: string): string {
        const payload = this.parseToken(token)

        if (!payload.sub) {
            throw new Error('Token subject is missing')
        }

        return payload.sub
    }

    private parseToken(token: string): JwtPayload {
        const parts = token.split('.')

        if (parts.length !== 3) {
            throw new Error('Invalid token format')
        }

        const [encodedHeader, encodedPayload, signature] = parts
        const unsignedToken = `${encodedHeader}.${encodedPayload}`
        const expectedSignature = this.sign(unsignedToken)

        if (!this.safeEqual(signature, expectedSignature)) {
            throw new Error('Invalid token signature')
        }

        const payload = this.base64UrlDecode<JwtPayload>(encodedPayload)

        if (payload.exp && payload.exp <= Math.floor(Date.now() / 1000)) {
            throw new Error('Token is expired')
        }

        return payload
    }

    private sign(unsignedToken: string): string {
        return createHmac('sha256', this.config.jwtSecretKey)
            .update(unsignedToken)
            .digest('base64url')
    }

    private safeEqual(left: string, right: string): boolean {
        const leftBuffer = Buffer.from(left)
        const rightBuffer = Buffer.from(right)

        if (leftBuffer.length !== rightBuffer.length) {
            return false
        }

        return timingSafeEqual(leftBuffer, rightBuffer)
    }

    private base64UrlEncode(value: unknown): string {
        return Buffer.from(JSON.stringify(value)).toString('base64url')
    }

    private base64UrlDecode<T>(value: string): T {
        return JSON.parse(Buffer.from(value, 'base64url').toString('utf8')) as T
    }
}
