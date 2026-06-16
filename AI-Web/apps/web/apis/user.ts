import request from '@/lib/request'

export const user = {
  login: <T>(url: string, body: unknown) =>
    request<T>(url, { method: 'POST', body }),

  register: <T>(url: string, body: unknown) =>
    request<T>(url, { method: 'POST', body }),

  getUserInfo: <T>(url: string) =>
    request<T>(url, { method: 'GET' }),
}
