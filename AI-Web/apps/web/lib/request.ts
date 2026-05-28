import { toast } from 'sonner'
import type { ApiResponse, RequestOptions } from '@/types/req'

async function request<T>(url: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
  const { method = 'GET', body, ...rest } = options
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? ''
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null

  const res = await fetch(`${baseUrl}${url}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    ...rest,
  })

  if (res.status === 401) {
    if (typeof window !== 'undefined') {
      window.location.href = '/login'
    }

    throw new Error('Unauthorized')
  }

  if (res.status === 422 && !res.ok) {
    toast.error('Invalid parameters', {
      position: 'top-center',
      duration: 2000,
      description: 'Please check your input and try again.',
    })
  }

  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`)
  }

  const json: ApiResponse<T> = await res.json()

  if (json.code === 500) {
    toast.error('Request failed', {
      description: json.message,
      position: 'top-center',
    })
  }

  return json
}

export default request
