<template>
  <div class="register-container flex h-screen items-center justify-center bg-gradient-to-br from-blue-400 to-purple-600">
    <div class="register-card w-full max-w-md rounded-lg bg-white p-8 shadow-lg">
      <h2 class="mb-6 text-center text-2xl font-bold text-gray-800">注册</h2>
      <el-form ref="formRef" :model="form" label-width="auto" @submit.prevent="onSubmit">
        <el-form-item label="用户名" prop="username" :rules="[{ required: true, message: '请输入用户名' }]">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="密码" prop="password" :rules="[{ required: true, message: '请输入密码' }]">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>

        <el-form-item label="年龄">
          <el-input-number v-model="form.age" :min="1" :max="120" placeholder="请输入年龄" />
        </el-form-item>

        <el-form-item label="性别">
          <el-radio-group v-model="form.sex">
            <el-radio :value="0">男</el-radio>
            <el-radio :value="1">女</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="邮箱">
          <el-input v-model="form.email" type="email" placeholder="请输入邮箱" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" native-type="submit" class="w-full">注册</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { reactive, ref } from 'vue'
import type { FormInstance } from 'element-plus'
import { register } from '@/api/user'
import type { RegisterForm } from '@/type/user'

const form = reactive<RegisterForm>({
  username: '',
  password: '',
  age: 1,
  email: '',
  sex: 0,
})

const formRef = ref<FormInstance>()

const onSubmit = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  await register(form)
}
</script>

<style scoped>
.register-container {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.register-card {
  box-shadow: 0 10px 25px rgb(0 0 0 / 10%);
}
</style>
