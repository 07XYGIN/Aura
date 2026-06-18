export const AUTH_TOKEN_COOKIE = 'aura_token'

export const setAuthTokenCookie = (token: string) => {
  document.cookie = `${AUTH_TOKEN_COOKIE}=${encodeURIComponent(token)}; Path=/; SameSite=Lax`
}

export const clearAuthTokenCookie = () => {
  document.cookie = `${AUTH_TOKEN_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`
}
