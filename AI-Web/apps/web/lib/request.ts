import { toast } from 'sonner'
import type { ApiResponse, RequestOptions } from '@/types/api'
import { useUserStore } from '@/store/user'

const redirectToLogin = (message = '登录已过期或非法，请重新登录') => {
  useUserStore.getState().logout()

  if (typeof window !== 'undefined') {
    toast.error(message, {
      position: 'top-center',
    })

    const pathname = window.location.pathname
    if (pathname !== '/login') {
      window.location.replace(`/login?redirect=${encodeURIComponent(pathname)}&reason=invalid`)
    }
  }
}

async function request<T>(url: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
  const { method = 'GET', body, ...rest } = options
  const baseUrl = process.env.NEXT_PUBLIC_BFF_URL ?? process.env.NEXT_PUBLIC_API_URL ?? ''
  const token = useUserStore.getState().token

  let res: Response

  try {
    res = await fetch(`${baseUrl.replace(/\/+$/, '')}${url}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      ...rest,
    })
  } catch {
    throw new Error('Network request failed')
  }

  if (res.status === 401) {
    redirectToLogin()
    throw new Error('Unauthorized')
  }

  if (res.status === 422 && !res.ok) {
    toast.error('Invalid parameters', {
      position: 'top-center',
      duration: 2000,
      description: 'Please check your input and try again.',
    })
  }

  let json: ApiResponse<T>

  try {
    json = await res.json()
  } catch {
    throw new Error(`Request failed: ${res.status}`)
  }

  if (!res.ok) {
    throw new Error(json.message || `Request failed: ${res.status}`)
  }

  if (json.code === 401) {
    redirectToLogin(json.message)
    throw new Error(json.message || 'Unauthorized')
  }

  if (json.code === 500) {
    toast.error('Request failed', {
      description: json.message,
      position: 'top-center',
    })
  }

  return json
}

export default request
