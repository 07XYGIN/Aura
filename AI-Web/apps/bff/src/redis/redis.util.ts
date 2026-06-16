import { Injectable, OnModuleDestroy } from '@nestjs/common'
import Redis from 'ioredis'
import { AppConfigService } from '../config/app-config.service'

@Injectable()
export class RedisUtil implements OnModuleDestroy {
    private readonly client: Redis

    constructor(config: AppConfigService) {
        this.client = new Redis({
            host: config.redisHost,
            port: config.redisPort,
            db: config.redisDatabase,
            password: config.redisPassword,
            lazyConnect: true,
            maxRetriesPerRequest: 1,
        })
    }

    async set(key: string, value: string, ttlSeconds?: number): Promise<void> {
        if (ttlSeconds && ttlSeconds > 0) {
            await this.client.set(key, value, 'EX', ttlSeconds)
            return
        }

        await this.client.set(key, value)
    }

    async get(key: string): Promise<string | null> {
        return this.client.get(key)
    }

    async delete(key: string): Promise<number> {
        return this.client.del(key)
    }

    onModuleDestroy(): void {
        this.client.disconnect()
    }
}
