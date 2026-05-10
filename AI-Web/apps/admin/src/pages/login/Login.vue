<template>
  <div class="login-container flex justify-center items-center h-screen bg-gradient-to-br from-blue-400 to-purple-600">
    <div class="login-card bg-white p-8 rounded-lg shadow-lg max-w-md w-full">
      <h2 class="text-2xl font-bold text-center mb-6 text-gray-800">登录</h2>
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

      <p class="text-center mt-4 text-gray-600">
        没有账号？
        <span class="text-blue-500 cursor-pointer hover:underline" @click="goToRegister">去注册</span>
      </p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance } from 'element-plus'
import { login } from '@/api/user'
import {useUserStore} from "@/store/modules/user.ts";
import type {LoginForm} from '@ai-web/types/main.ts'
const user = useUserStore()

const form = reactive<LoginForm>({
  username: '',
  password: '',
  age: 1,
  gender: '',
  email: '',
})

const formRef = ref<FormInstance>()
const router = useRouter()
const loginSubmit = async (data:LoginForm)=>{
  const {token} = await login(data)
  if(!token) return
  user.setToken(token)
  await router.push('/')
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
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
}
</style>
