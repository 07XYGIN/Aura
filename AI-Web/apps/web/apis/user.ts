import request from '@/lib/request'
import type { UserProfile } from '@ai-web/types'

export const user = {
  login: <T>(url: string, body: unknown) =>
    request<T>(url, { method: 'POST', body }),

  register: <T>(url: string, body: unknown) =>
    request<T>(url, { method: 'POST', body }),

  getUserInfo: <T = UserProfile>() =>
    request<T>('/api/user/userInfo', { method: 'GET' }),

  updateInfo: (body: UserProfile) =>
    request<UserProfile>('/api/user/updateInfo', { method: 'PUT', body }),

  deleteUser: (username: string) =>
    request('/api/user/' + encodeURIComponent(username), { method: 'DELETE' }),

  logout: (userId: string) =>
    request('/api/user/logout/' + encodeURIComponent(userId), { method: 'GET' }),
}
