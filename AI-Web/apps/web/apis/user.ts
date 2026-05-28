import request from '@/lib/request'

export const user = {
  login: <T>(url: string, body: unknown) =>
    request<T>(url, { method: 'POST', body }),

  post: <T>(url: string, body: unknown) =>
    request<T>(url, { method: 'POST', body }),

  put: <T>(url: string, body: unknown) =>
    request<T>(url, { method: 'PUT', body }),

  delete: <T>(url: string) =>
    request<T>(url, { method: 'DELETE' }),
}
