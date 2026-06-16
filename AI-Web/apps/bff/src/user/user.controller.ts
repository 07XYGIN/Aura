import { Controller, Get, Headers } from '@nestjs/common'
import axios from 'axios'
import { AppConfigService } from '../config/app-config.service'

@Controller('user')
export class UserController {
    constructor(private readonly config: AppConfigService) {}

    @Get('info')
    async getUserInfo(@Headers('authorization') authorization?: string): Promise<any> {
        const res = await axios.get(`${this.config.coreServiceUrl}/user/userInfo`, {
            headers: authorization ? { Authorization: authorization } : undefined,
        })

        return res.data
    }
}
