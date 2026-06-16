import { Body, Controller, Delete, Get, Headers, HttpCode, Param, Post, Put } from '@nestjs/common'
import { Public } from '../common/decorators/public.decorator'
import type { ApiResponse } from '../common/interfaces/api-response.interface'
import { UserService } from './user.service'

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
        @Param('userId') userId: string,
        @Headers('authorization') authorization?: string,
    ): Promise<ApiResponse> {
        return this.userService.logout(userId, authorization)
    }

    @Get('userInfo')
    getUserInfo(@Headers('authorization') authorization?: string): Promise<ApiResponse> {
        return this.userService.getUserInfo(authorization)
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
