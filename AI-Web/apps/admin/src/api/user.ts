import request from '@/utils/requests'
import type { LoginResponse, User } from '@/type/user'
import type { LoginForm } from '@ai-web/types'

/**
 * 注册
 */
export const register = (data: User) => {
  return request({
    url: '/api/user/register',
    method: 'POST',
    data,
  })
}

/**
 * 用户登录
 */
export const login = (data: LoginForm): Promise<LoginResponse> => {
  return request({
    url: '/api/user/login',
    method: 'POST',
    data,
  })
}

/**
 * 用户退出
 */
export const logout = (id: string) => {
  return request({
    url: `/api/user/logout/${id}`,
    method: 'GET',
  })
}

/**
 * 获取用户信息
 */
export const getUserInfo = () => {
  return request({
    url: '/api/user/userInfo',
    method: 'GET',
  })
}

/**
 * 更新用户信息
 */
export const updateUserInfo = (data: User) => {
  return request({
    url: '/api/user/updateInfo',
    method: 'PUT',
    data,
  })
}

/**
 * 用户注销
 */
export const logoutUser = (userId: string) => {
  return request({
    url: `/api/user/${userId}`,
    method: 'DELETE',
  })
}
