import { BadRequestException, HttpException, Injectable } from '@nestjs/common'
import axios from 'axios'
import { AppConfigService } from '../config/app-config.service'

type ResolveAdcodeInput = {
    city?: string
    longitude?: string
    latitude?: string
    ip?: string
}

type AmapBaseResponse = {
    status?: string
    info?: string
    infocode?: string
}

type AmapRegeoResponse = AmapBaseResponse & {
    regeocode?: {
        addressComponent?: {
            province?: string
            city?: string | string[]
            district?: string
            adcode?: string
            citycode?: string
        }
    }
}

type AmapDistrictResponse = AmapBaseResponse & {
    districts?: Array<{
        name?: string
        level?: string
        citycode?: string
        adcode?: string
    }>
}

type AmapIpResponse = AmapBaseResponse & {
    province?: string
    city?: string | string[]
    adcode?: string
    rectangle?: string
}

type CityAdcodeResult = {
    adcode: string
    province?: string
    city?: string
    district?: string
    citycode?: string
    source: 'regeo' | 'district' | 'ip'
}

@Injectable()
export class LocationService {
    private readonly amapBaseUrl = 'https://restapi.amap.com/v3'

    constructor(private readonly config: AppConfigService) {}

    async resolveAdcode(input: ResolveAdcodeInput): Promise<CityAdcodeResult> {
        this.assertAmapKey()

        const coordinate = this.parseCoordinate(input.longitude, input.latitude)
        if (coordinate) {
            return this.resolveByCoordinate(coordinate.longitude, coordinate.latitude)
        }

        const city = input.city?.trim()
        if (city) {
            return this.resolveByCity(city)
        }

        return this.resolveByIp(input.ip)
    }

    private async resolveByCoordinate(longitude: number, latitude: number): Promise<CityAdcodeResult> {
        const data = await this.getAmap<AmapRegeoResponse>('/geocode/regeo', {
            location: `${longitude},${latitude}`,
            extensions: 'base',
            radius: '1000',
        })
        const component = data.regeocode?.addressComponent
        const adcode = component?.adcode?.trim()

        if (!adcode) {
            throw new HttpException('Amap did not return adcode for current location', 502)
        }

        return {
            adcode,
            province: component?.province,
            city: this.firstText(component?.city),
            district: component?.district,
            citycode: component?.citycode,
            source: 'regeo',
        }
    }

    private async resolveByCity(city: string): Promise<CityAdcodeResult> {
        const data = await this.getAmap<AmapDistrictResponse>('/config/district', {
            keywords: city,
            subdistrict: '0',
            extensions: 'base',
        })
        const district = data.districts?.find((item) => item.adcode)

        if (!district?.adcode) {
            throw new BadRequestException('city adcode not found')
        }

        return {
            adcode: district.adcode,
            city: district.name,
            citycode: district.citycode,
            source: 'district',
        }
    }

    private async resolveByIp(ip?: string): Promise<CityAdcodeResult> {
        const publicIp = this.publicIp(ip)
        if (!publicIp) {
            throw new BadRequestException('client public ip is required for IP location')
        }

        const data = await this.getAmap<AmapIpResponse>('/ip', { ip: publicIp })
        const adcode = data.adcode?.trim()

        if (!adcode) {
            throw new HttpException('Amap did not return adcode from IP location', 502)
        }

        return {
            adcode,
            province: data.province,
            city: this.firstText(data.city),
            source: 'ip',
        }
    }

    private async getAmap<T extends AmapBaseResponse>(
        path: string,
        params: Record<string, string>,
    ): Promise<T> {
        const response = await axios.get<T>(`${this.amapBaseUrl}${path}`, {
            params: {
                ...params,
                key: this.config.amapKey,
            },
            timeout: 5000,
        })

        if (response.data.status !== '1') {
            throw new HttpException(
                response.data.info || `Amap request failed: ${response.data.infocode || 'unknown'}`,
                502,
            )
        }

        return response.data
    }

    private parseCoordinate(
        longitudeValue?: string,
        latitudeValue?: string,
    ): { longitude: number; latitude: number } | undefined {
        if (!longitudeValue || !latitudeValue) {
            return undefined
        }

        const longitude = Number(longitudeValue)
        const latitude = Number(latitudeValue)

        if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
            throw new BadRequestException('invalid location coordinates')
        }

        if (longitude < -180 || longitude > 180 || latitude < -90 || latitude > 90) {
            throw new BadRequestException('location coordinates out of range')
        }

        return {
            longitude: Number(longitude.toFixed(6)),
            latitude: Number(latitude.toFixed(6)),
        }
    }

    private assertAmapKey(): void {
        if (!this.config.amapKey) {
            throw new HttpException('AMAP_KEY is not configured', 500)
        }
    }

    private firstText(value?: string | string[]): string | undefined {
        if (Array.isArray(value)) {
            return value.find((item) => item.trim().length > 0)
        }

        return value || undefined
    }

    private publicIp(ip?: string): string | undefined {
        if (!ip) {
            return undefined
        }

        const normalized = ip.replace(/^::ffff:/, '').trim()
        if (
            normalized === '127.0.0.1' ||
            normalized === '::1' ||
            normalized.startsWith('10.') ||
            normalized.startsWith('192.168.') ||
            /^172\.(1[6-9]|2\d|3[0-1])\./.test(normalized)
        ) {
            return undefined
        }

        return normalized
    }
}
