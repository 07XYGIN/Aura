import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { user } from '@/apis/user'

interface UserState {
    token: string
    setToken: (token: string) => void
    userInfo: User
    getUserInfo: () => Promise<void>
}

interface User {
    username?: string
    email?: string
    age?: number
    sex?: number
}

export const useUserStore = create<UserState>()(
    persist(
        (set) => ({
            token: '',
            userInfo: {},
            setToken: (token) => set({ token }),
            getUserInfo: async () => {
                const response = await user.getUserInfo<User>('/user/userInfo')
                set({ userInfo: response.data })
            },
        }),
        {
            name: 'user-info',
        },
    ),
)
