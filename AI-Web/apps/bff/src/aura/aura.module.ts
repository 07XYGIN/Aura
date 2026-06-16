import { Module } from '@nestjs/common'
import { AdminAuraController } from './admin-aura.controller'
import { AuraController } from './aura.controller'
import { AuraService } from './aura.service'

@Module({
    controllers: [AuraController, AdminAuraController],
    providers: [AuraService],
})
export class AuraModule {}
