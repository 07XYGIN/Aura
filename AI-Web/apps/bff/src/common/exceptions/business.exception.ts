import { HttpException, HttpStatus } from '@nestjs/common'

export class BusinessException extends HttpException {
    constructor(message: string, statusCode = HttpStatus.BAD_REQUEST) {
        super(message, statusCode)
    }
}
