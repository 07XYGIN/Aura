import { Body, Controller, HttpCode, Post, Req, Res } from '@nestjs/common'
import type { Request, Response } from 'express'
import type { AuthUser } from '../auth/interfaces/auth-user.interface'
import { ChatService } from './chat.service'

type RequestWithUser = Request & { user: AuthUser }

type ChatSseBody = {
    message?: unknown
    clientMessageId?: unknown
    sessionId?: unknown
    attachmentIds?: unknown
    cityAdcode?: unknown
}

@Controller('chat')
export class ChatController {
    constructor(private readonly chatService: ChatService) {}

    @HttpCode(200)
    @Post('sse')
    streamSse(
        @Body() body: ChatSseBody,
        @Req() request: RequestWithUser,
        @Res() response: Response,
    ): Promise<void> {
        return this.chatService.streamSse(
            {
                message: body.message,
                clientMessageId: body.clientMessageId,
                sessionId: body.sessionId,
                attachmentIds: body.attachmentIds,
                cityAdcode: body.cityAdcode,
                userId: request.user.userId,
                token: request.user.token,
            },
            response,
        )
    }

    @HttpCode(200)
    @Post('attachments')
    uploadAttachments(
        @Body() body: unknown,
        @Req() request: RequestWithUser,
    ): Promise<unknown> {
        return this.chatService.uploadAttachments(body, request.user.userId)
    }
}
