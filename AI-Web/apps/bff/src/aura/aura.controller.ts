import { Body, Controller, Delete, Get, HttpCode, Param, Post, Query, Req } from '@nestjs/common'
import type { Request } from 'express'
import type { AuthUser } from '../auth/interfaces/auth-user.interface'
import type { ApiResponse } from '../common/interfaces/api-response.interface'
import { AuraService } from './aura.service'

type RequestWithUser = Request & { user: AuthUser }

@Controller('aura')
export class AuraController {
    constructor(private readonly auraService: AuraService) {}

    @Get('initial-setting')
    getInitialSetting(
        @Req() request: RequestWithUser,
        @Query('sessionId') sessionId?: string,
    ): Promise<ApiResponse> {
        return this.auraService.getInitialSetting(request.user.userId, request.user.token, sessionId)
    }

    @HttpCode(200)
    @Post('initial-setting')
    saveInitialSetting(
        @Body() body: unknown,
        @Req() request: RequestWithUser,
    ): Promise<ApiResponse> {
        return this.auraService.saveInitialSetting(body, request.user.userId, request.user.token)
    }

    @Get('relationship')
    getRelationshipStatus(
        @Req() request: RequestWithUser,
        @Query('message') message?: string,
    ): Promise<ApiResponse> {
        return this.auraService.getRelationshipStatus(request.user.userId, request.user.token, message)
    }

    @Get('sessions/current/messages')
    getCurrentSessionMessages(@Req() request: RequestWithUser): Promise<ApiResponse> {
        return this.auraService.getCurrentSessionMessages(request.user.userId)
    }

    @Delete('sessions/current/messages')
    clearCurrentSessionMessages(@Req() request: RequestWithUser): Promise<ApiResponse> {
        return this.auraService.clearCurrentSessionMessages(request.user.userId, request.user.token)
    }

    @Delete('sessions/current/messages/:messageId')
    deleteCurrentSessionMessage(
        @Param('messageId') messageId: string,
        @Req() request: RequestWithUser,
    ): Promise<ApiResponse> {
        return this.auraService.deleteCurrentSessionMessage(request.user.userId, messageId)
    }

    @Get('memories')
    getMemories(
        @Req() request: RequestWithUser,
        @Query('page') page = '1',
        @Query('pageSize') pageSize = '10',
    ): Promise<ApiResponse> {
        return this.auraService.getMemories(request.user.userId, page, pageSize)
    }

    @Delete('memories')
    clearMemories(@Req() request: RequestWithUser): Promise<ApiResponse> {
        return this.auraService.clearMemories(request.user.userId, request.user.token)
    }

    @Delete('memories/:memoryId')
    deleteMemory(
        @Param('memoryId') memoryId: string,
        @Req() request: RequestWithUser,
    ): Promise<ApiResponse> {
        return this.auraService.deleteMemory(request.user.userId, memoryId)
    }

    @Get('memories/search')
    searchMemories(
        @Req() request: RequestWithUser,
        @Query('query') query?: string,
        @Query('k') k = '5',
    ): Promise<ApiResponse> {
        return this.auraService.searchMemories(request.user.userId, query, k)
    }

    @Get('emotion')
    getEmotion(
        @Req() request: RequestWithUser,
        @Query('message') message?: string,
    ): Promise<ApiResponse> {
        return this.auraService.getEmotion(request.user.userId, request.user.token, message)
    }
}
