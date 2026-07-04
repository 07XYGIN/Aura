import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/modules/user'
import router from '@/router'

const request = axios.create({
  baseURL: import.meta.env.VITE_AI_SERVICE_URL || 'http://localhost:8000',
})

let authMessageVisible = false

const redirectToLogin = async (message = '登录已过期或非法，请重新登录') => {
  const userStore = useUserStore()
  userStore.clearToken()

  if (!authMessageVisible) {
    authMessageVisible = true
    ElMessage.error({
      message,
      onClose: () => {
        authMessageVisible = false
      },
    })
  }

  if (router.currentRoute.value.name !== 'login' && router.currentRoute.value.name !== 'register') {
    await router.replace({
      path: '/login',
      query: { redirect: router.currentRoute.value.fullPath },
    })
  }
}

request.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => {
    console.error(error)
    return Promise.reject(error)
  },
)

request.interceptors.response.use(
  (response) => {
    if (response.data.code >= 200 && response.data.code < 300) {
      return response.data
    }

    if (response.data.code === 401) {
      void redirectToLogin(response.data.message)
      return Promise.reject(new Error(response.data.message || 'Unauthorized'))
    }

    if (response.data.code >= 500 || response.data.code === 422) {
      ElMessage({
        message: response.data.message,
        type: 'error',
      })
    } else {
      ElMessage({
        message: response.data.message,
        type: 'error',
      })
    }

    return response.data
  },
  (error) => {
    console.error(error)

    if (error.response?.status === 401 || error.response?.data?.code === 401) {
      void redirectToLogin(error.response?.data?.message)
      return Promise.reject(error)
    }

    ElMessage.error(error.message || '请求失败')
    return Promise.reject(error)
  },
)

export default request
