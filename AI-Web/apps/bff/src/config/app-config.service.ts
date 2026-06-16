import { Injectable } from '@nestjs/common'

@Injectable()
export class AppConfigService {
    get port(): number {
        return Number(this.get('PORT', '3001'))
    }

    get jwtSecretKey(): string {
        return this.get('JWT_SECRET_KEY', 'change-me-to-a-strong-32-byte-secret-key')
    }

    get jwtExpireTime(): number {
        return Number(this.get('JWT_EXPIRE_TIME', '86400000'))
    }

    get redisHost(): string {
        return this.get('REDIS_HOST', 'localhost')
    }

    get redisPort(): number {
        return Number(this.get('REDIS_PORT', '6379'))
    }

    get redisDatabase(): number {
        return Number(this.get('REDIS_DATABASE', '0'))
    }

    get redisPassword(): string | undefined {
        return process.env.REDIS_PASSWORD || undefined
    }

    get coreServiceUrl(): string {
        return this.get('CORE_SERVICE_URL', 'http://127.0.0.1:8080')
    }

    get aiServiceUrl(): string {
        return this.get('AI_SERVICE_URL', 'http://127.0.0.1:8000')
    }

    private get(key: string, fallback: string): string {
        return process.env[key] || fallback
    }
}
