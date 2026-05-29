import type { LoginForm as LoginFormValues } from '@ai-web/types'

export type AuthMode = 'login' | 'register'

export type AuthSex = 'male' | 'female' | 'other' | ''

export type AuthFormValues = Partial<
  Omit<LoginFormValues, 'age' | 'gender'> & {
    age: string
    sex: AuthSex
  }
>

export type SexOption = {
  label: string
  value: Exclude<AuthSex, ''>
}
