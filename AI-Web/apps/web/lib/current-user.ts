import { useUserStore } from '@/store/user'

type JwtPayload = {
  sub?: string
  userId?: string
  id?: string
}

const decodeTokenPayload = (token: string): JwtPayload | null => {
  const [, payload] = token.split('.')
  if (!payload || typeof window === 'undefined') {
    return null
  }

  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    return JSON.parse(window.atob(padded)) as JwtPayload
  } catch {
    return null
  }
}

export const getCurrentUserId = () => {
  const { token, userInfo } = useUserStore.getState()
  const storeUserId = userInfo.id?.trim()
  if (storeUserId) {
    return storeUserId
  }

  const payload = token ? decodeTokenPayload(token) : null
  return payload?.userId?.trim() || payload?.id?.trim() || payload?.sub?.trim() || ''
}
