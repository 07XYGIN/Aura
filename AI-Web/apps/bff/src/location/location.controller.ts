import { Controller, Get, Query, Req } from '@nestjs/common'
import type { Request } from 'express'
import { LocationService } from './location.service'

@Controller('location')
export class LocationController {
    constructor(private readonly locationService: LocationService) {}

    @Get('adcode')
    resolveAdcode(
        @Query('city') city: string | undefined,
        @Query('longitude') longitude: string | undefined,
        @Query('latitude') latitude: string | undefined,
        @Req() request: Request,
    ) {
        return this.locationService.resolveAdcode({
            city,
            longitude,
            latitude,
            ip: this.clientIp(request),
        })
    }

    private clientIp(request: Request): string | undefined {
        const forwardedFor = request.headers['x-forwarded-for']
        const firstForwardedIp = Array.isArray(forwardedFor)
            ? forwardedFor[0]
            : forwardedFor?.split(',')[0]

        return (firstForwardedIp || request.ip || request.socket.remoteAddress || undefined)?.trim()
    }
}
