import { Body, Controller, HttpCode, Post, Req, Res } from '@nestjs/common'
import type { Request, Response } from 'express'
import type { AuthUser } from '../auth/interfaces/auth-user.interface'
import { ChatService } from './chat.service'

type RequestWithUser = Request & { user: AuthUser }

type ChatSseBody = {
    message?: unknown
    clientMessageId?: unknown
    sessionId?: unknown
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
                userId: request.user.userId,
                token: request.user.token,
            },
            response,
        )
    }
}
