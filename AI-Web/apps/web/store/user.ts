import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { user } from '@/apis/user'
import type { UserProfile } from '@ai-web/types'
import { clearAuthTokenCookie, setAuthTokenCookie } from '@/lib/auth-token'

interface UserState {
    token: string
    setToken: (token: string) => void
    logout: () => void
    userInfo: UserProfile
    getUserInfo: () => Promise<void>
    logoutRemote: () => Promise<void>
    updateUserInfo: (profile: UserProfile) => Promise<void>
    deleteCurrentUser: () => Promise<void>
}

export const useUserStore = create<UserState>()(
    persist(
        (set) => ({
            token: '',
            userInfo: {},
            setToken: (token) => {
                setAuthTokenCookie(token)
                set({ token })
            },
            logout: () => {
                clearAuthTokenCookie()
                set({ token: '', userInfo: {} })
            },
            getUserInfo: async () => {
                const response = await user.getUserInfo<UserProfile>()
                set({ userInfo: response.data ?? {} })
            },
            logoutRemote: async () => {
                const userId = useUserStore.getState().userInfo.id
                if (userId) {
                    await user.logout(userId)
                }
                clearAuthTokenCookie()
                set({ token: '', userInfo: {} })
            },
            updateUserInfo: async (profile) => {
                await user.updateInfo(profile)
                set((state) => ({
                    userInfo: {
                        ...state.userInfo,
                        ...profile,
                    },
                }))
            },
            deleteCurrentUser: async () => {
                const username = useUserStore.getState().userInfo.username
                if (!username) {
                    throw new Error('Missing username')
                }

                await user.deleteUser(username)
                clearAuthTokenCookie()
                set({ token: '', userInfo: {} })
            },
        }),
        {
            name: 'user-info',
        },
    ),
)
