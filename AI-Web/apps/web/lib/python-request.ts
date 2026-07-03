import { toast } from 'sonner'
import type { ApiResponse, RequestOptions } from '@/types/api'
import { useUserStore } from '@/store/user'

export const getPythonApiBaseUrl = () =>
  (process.env.NEXT_PUBLIC_AI_SERVICE_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

const redirectToLogin = (message = 'Login expired. Please sign in again.') => {
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

const getErrorMessage = (value: unknown, fallback: string) => {
  if (typeof value === 'object' && value !== null) {
    if ('message' in value && typeof value.message === 'string') {
      return value.message
    }
    if ('msg' in value && typeof value.msg === 'string') {
      return value.msg
    }
    if ('detail' in value) {
      const detail = value.detail
      if (typeof detail === 'string') {
        return detail
      }
      if (Array.isArray(detail)) {
        return detail.map((item) => JSON.stringify(item)).join('; ')
      }
    }
  }

  return fallback
}

async function pythonRequest<T>(
  url: string,
  options: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const { method = 'GET', body, ...rest } = options
  const token = useUserStore.getState().token

  let res: Response

  try {
    res = await fetch(`${getPythonApiBaseUrl()}${url}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      ...rest,
    })
  } catch {
    throw new Error('Python service request failed')
  }

  let json: ApiResponse<T> | unknown

  try {
    json = await res.json()
  } catch {
    throw new Error(`Python service request failed: ${res.status}`)
  }

  if (res.status === 401) {
    const message = getErrorMessage(json, 'Unauthorized')
    redirectToLogin(message)
    throw new Error(message)
  }

  if (!res.ok) {
    throw new Error(getErrorMessage(json, `Python service request failed: ${res.status}`))
  }

  const response = json as ApiResponse<T>
  if (response.code < 200 || response.code >= 300) {
    const message = response.message ?? response.msg ?? 'Python service request failed'
    toast.error(message, { position: 'top-center' })
    throw new Error(message)
  }

  return response
}

export default pythonRequest
