import { NextRequest, NextResponse } from 'next/server'
import { AUTH_TOKEN_COOKIE } from '@/lib/auth-token'

const PUBLIC_PATHS = new Set(['/login'])

const isTokenExpired = (token: string) => {
  const [, payload] = token.split('.')
  if (!payload) return true

  try {
    const normalizedPayload = payload.replace(/-/g, '+').replace(/_/g, '/')
    const decoded = JSON.parse(atob(normalizedPayload)) as { exp?: number }
    return typeof decoded.exp === 'number' && decoded.exp <= Math.floor(Date.now() / 1000)
  } catch {
    return true
  }
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl

  if (PUBLIC_PATHS.has(pathname)) {
    return NextResponse.next()
  }

  const token = request.cookies.get(AUTH_TOKEN_COOKIE)?.value

  if (!token || isTokenExpired(token)) {
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = '/login'
    loginUrl.searchParams.set('redirect', `${pathname}${request.nextUrl.search}`)
    loginUrl.searchParams.set('reason', token ? 'expired' : 'missing')
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)'],
}
