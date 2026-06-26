export interface LoginForm {
    username: string
    password: string
    age?: number
    sex?: 0 | 1
    email?: string
    code?: string
    inviteCode?: string
}

export interface UserProfile {
    id?: string
    username?: string
    password?: string
    age?: number
    sex?: 0 | 1
    email?: string
}
