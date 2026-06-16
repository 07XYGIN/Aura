export interface User {
  username: string
  password: string
  age: number
  sex?: 0 | 1
  email: string
}

export type UserInfo = User

export interface RegisterForm {
  username: string
  password: string
  age: number
  email: string
  sex?: 0 | 1
}

export interface LoginResponse {
  token: string
  message?: string
  // 其他字段按后端返回扩展
}
