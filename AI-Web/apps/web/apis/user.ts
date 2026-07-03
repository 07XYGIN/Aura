import pythonRequest from '@/lib/python-request'
import type { UserProfile } from '@ai-web/types'

export const user = {
  login: <T>(url: string, body: unknown) =>
    pythonRequest<T>(url, { method: 'POST', body }),

  register: <T>(url: string, body: unknown) =>
    pythonRequest<T>(url, { method: 'POST', body }),

  getUserInfo: <T = UserProfile>() =>
    pythonRequest<T>('/api/user/userInfo', { method: 'GET' }),

  updateInfo: (body: UserProfile) =>
    pythonRequest<UserProfile>('/api/user/updateInfo', { method: 'PUT', body }),

  deleteUser: (username: string) =>
    pythonRequest('/api/user/' + encodeURIComponent(username), { method: 'DELETE' }),

  logout: (userId: string) =>
    pythonRequest('/api/user/logout/' + encodeURIComponent(userId), { method: 'GET' }),
}
