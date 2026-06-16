import { HttpStatus } from '@nestjs/common'
import { BusinessException } from './business.exception'

export class LoginException extends BusinessException {
    constructor(message: string, statusCode = HttpStatus.UNAUTHORIZED) {
        super(message, statusCode)
    }
}
