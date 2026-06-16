import { Controller, Get, Param, Query, Req } from '@nestjs/common'
import type { Request } from 'express'
import type { AuthUser } from '../auth/interfaces/auth-user.interface'
import type { ApiResponse } from '../common/interfaces/api-response.interface'
import { AuraService } from './aura.service'

type RequestWithUser = Request & { user: AuthUser }

@Controller('admin/aura')
export class AdminAuraController {
    constructor(private readonly auraService: AuraService) {}

    @Get(':resource')
    getResourceList(
        @Param('resource') resource: string,
        @Query('userId') userId: string | undefined,
        @Query('keyword') keyword: string | undefined,
        @Query('page') page = '1',
        @Query('pageSize') pageSize = '10',
        @Req() request: RequestWithUser,
    ): Promise<ApiResponse> {
        return this.auraService.getAdminResourceList(resource, {
            userId,
            keyword,
            page,
            pageSize,
            token: request.user.token,
        })
    }
}
