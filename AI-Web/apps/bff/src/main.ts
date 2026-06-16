import { NestFactory } from '@nestjs/core'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { AppModule } from './app.module'
import { AppConfigService } from './config/app-config.service'

function loadLocalEnv() {
    const envPath = resolve(__dirname, '..', '.env')
    if (!existsSync(envPath)) {
        return
    }

    const envContent = readFileSync(envPath, 'utf8')
    for (const line of envContent.split(/\r?\n/)) {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith('#')) {
            continue
        }

        const separatorIndex = trimmed.indexOf('=')
        if (separatorIndex <= 0) {
            continue
        }

        const key = trimmed.slice(0, separatorIndex).trim()
        const value = trimmed.slice(separatorIndex + 1).trim()
        process.env[key] ??= value
    }
}

async function bootstrap() {
    loadLocalEnv()
    const app = await NestFactory.create(AppModule)
    const config = app.get(AppConfigService)

    app.setGlobalPrefix('api')
    app.enableCors()

    await app.listen(config.port)
}
void bootstrap()
