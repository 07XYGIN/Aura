<template>
  <div class="login-container flex h-screen items-center justify-center bg-gradient-to-br from-blue-400 to-purple-600">
    <div class="login-card w-full max-w-md rounded-lg bg-white p-8 shadow-lg">
      <h2 class="mb-6 text-center text-2xl font-bold text-gray-800">登录</h2>
      <el-form ref="formRef" :model="form" label-width="auto" @submit.prevent="onSubmit">
        <el-form-item label="用户名" prop="username" :rules="[{ required: true, message: '请输入用户名' }]">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="密码" prop="password" :rules="[{ required: true, message: '请输入密码' }]">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" native-type="submit" class="w-full">登录</el-button>
        </el-form-item>
      </el-form>

      <p class="mt-4 text-center text-gray-600">
        没有账号？
        <span class="cursor-pointer text-blue-500 hover:underline" @click="goToRegister">去注册</span>
      </p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance } from 'element-plus'
import { login } from '@/api/user'
import { useUserStore } from '@/store/modules/user'
import type { LoginForm } from '@ai-web/types'

const user = useUserStore()

const form = reactive<LoginForm>({
  username: '',
  password: '',
})

const formRef = ref<FormInstance>()
const router = useRouter()

const loginSubmit = async (data: LoginForm) => {
  const { token, message } = await login(data)
  if (!token) {
    ElMessage.error(message || '用户名或密码错误')
    return
  }
  user.setToken(token)
  const redirect = typeof router.currentRoute.value.query.redirect === 'string' ? router.currentRoute.value.query.redirect : '/'
  await router.push(redirect)
}

const onSubmit = () => {
  if (!formRef.value) return

  formRef.value.validate((valid) => {
    if (valid) {
      loginSubmit(form)
    }
  })
}

const goToRegister = () => {
  router.push('/register')
}
</script>

<style scoped>
.login-container {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  box-shadow: 0 10px 25px rgb(0 0 0 / 10%);
}
</style>
