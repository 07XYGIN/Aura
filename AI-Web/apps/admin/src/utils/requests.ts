import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/modules/user'
import router from '@/router'

const request = axios.create({
  baseURL: import.meta.env.VITE_BFF_URL || 'http://localhost:3001',
})

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
    const userStore = useUserStore()
    if (response.data.code >= 200 && response.data.code < 300) {
      return response.data
    } else if (response.data.code === 401) {
      ElMessage({
        message: response.data.message,
        type: 'error',
      })
      userStore.clearToken()
      router.push('/login')
    } else if (response.data.code >= 500 || response.data.code === 422) {
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
    ElMessage.error(error.message || '请求失败')
    return Promise.reject(error)
  },
)

export default request
