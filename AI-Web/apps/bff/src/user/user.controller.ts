import {
    Body,
    Controller,
    Delete,
    Get,
    Headers,
    HttpCode,
    Param,
    Post,
    Put,
    Query,
    Req,
} from '@nestjs/common'
import type { Request } from 'express'
import { Public } from '../common/decorators/public.decorator'
import type { ApiResponse } from '../common/interfaces/api-response.interface'
import type { AuthUser } from '../auth/interfaces/auth-user.interface'
import { UserService } from './user.service'

type RequestWithUser = Request & { user: AuthUser }

@Controller('user')
export class UserController {
    constructor(private readonly userService: UserService) {}

    @Public()
    @HttpCode(200)
    @Post('register')
    register(@Body() body: unknown): Promise<ApiResponse> {
        return this.userService.register(body)
    }

    @Public()
    @HttpCode(200)
    @Post('login')
    login(@Body() body: unknown): Promise<ApiResponse> {
        return this.userService.login(body)
    }

    @Get('logout/:userId')
    logout(
        @Req() request: RequestWithUser,
        @Headers('authorization') authorization?: string,
    ): Promise<ApiResponse> {
        return this.userService.logout(request.user.userId, authorization)
    }

    @Get('userInfo')
    getUserInfo(@Headers('authorization') authorization?: string): Promise<ApiResponse> {
        return this.userService.getUserInfo(authorization)
    }

    @Get('memoryList')
    getMemoryList(
        @Req() request: RequestWithUser,
        @Query('page') page = '1',
        @Query('pageSize') pageSize = '10',
    ): Promise<ApiResponse> {
        return this.userService.getMemoryList(request.user.userId, page, pageSize)
    }

    @Put('updateInfo')
    updateInfo(
        @Body() body: unknown,
        @Headers('authorization') authorization?: string,
    ): Promise<ApiResponse> {
        return this.userService.updateInfo(body, authorization)
    }

    @Delete(':username')
    deleteUser(
        @Param('username') username: string,
        @Headers('authorization') authorization?: string,
    ): Promise<ApiResponse> {
        return this.userService.deleteUser(username, authorization)
    }
}
