import type { LoginForm as LoginFormValues } from '@ai-web/types'

export type AuthMode = 'login' | 'register'

export type AuthSex = '1' | '0' | ''
export type UserSex = 0 | 1

export type AuthFormValues = Partial<
  Omit<LoginFormValues, 'age' | 'sex'> & {
    age: string
    sex: AuthSex
    inviteCode: string
  }
>

export type SexOption = {
  label: string
  value: Exclude<AuthSex, ''>
}
