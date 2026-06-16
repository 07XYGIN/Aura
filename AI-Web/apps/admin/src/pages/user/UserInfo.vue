<template>
  <div class="user-info-page">
    <section class="page-title">
      <div>
        <p class="eyebrow">个人中心</p>
        <h1>账号资料</h1>
      </div>
    </section>

    <section class="profile-layout">
      <aside class="profile-summary">
        <el-avatar :size="72" class="profile-avatar">
          {{ usernameInitial }}
        </el-avatar>
        <div>
          <h2>{{ form.username || '未设置用户名' }}</h2>
          <p>{{ form.email || '未设置邮箱' }}</p>
        </div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="年龄">
            {{ form.age }}
          </el-descriptions-item>
          <el-descriptions-item label="性别">
            {{ sexLabel }}
          </el-descriptions-item>
        </el-descriptions>
      </aside>

      <section class="profile-form-panel">
        <div class="panel-header">
          <h2>基础信息</h2>
          <el-tag type="info" effect="plain">前端保存</el-tag>
        </div>

        <el-form :model="form" label-width="92px" class="profile-form">
          <el-form-item label="用户名">
            <el-input v-model="form.username" clearable placeholder="请输入用户名" disabled />
          </el-form-item>

          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" clearable show-password placeholder="请输入密码" />
          </el-form-item>

          <el-form-item label="年龄">
            <el-input-number v-model="form.age" :min="1" :max="120" />
          </el-form-item>

          <el-form-item label="性别">
            <el-radio-group v-model="form.sex">
              <el-radio :value="0">男</el-radio>
              <el-radio :value="1">女</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="邮箱">
            <el-input v-model="form.email" type="email" clearable placeholder="请输入邮箱" />
          </el-form-item>

          <el-form-item class="form-actions">
            <el-button type="primary" @click="handleSave">保存修改</el-button>
            <el-button @click="resetForm">重置</el-button>
            <el-button type="danger" plain :loading="logoutLoading" @click="handleLogout">注销</el-button>
          </el-form-item>
        </el-form>
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import { logoutUser, updateUserInfo } from '@/api/user'
import { useUserStore } from '@/store/modules/user'
import type { UserInfo } from '@/type/user'

const router = useRouter()
const userStore = useUserStore()
const { userInfo } = storeToRefs(userStore)

const logoutLoading = ref(false)

const form = reactive<UserInfo>({
  username: '',
  password: '',
  age: 1,
  sex: 0,
  email: '',
})

const syncForm = (data: UserInfo) => {
  form.username = data.username ?? ''
  form.password = data.password ?? ''
  form.age = data.age ?? 1
  form.sex = data.sex ?? 0
  form.email = data.email ?? ''
}

const usernameInitial = computed(() => form.username.trim().slice(0, 1).toUpperCase() || 'U')
const sexLabel = computed(() => (form.sex === 1 ? '女' : '男'))

const handleSave = () => {
  updateUserInfo(form).then(() => {
    userStore.updateUserInfo(form)
    ElMessage.success('个人信息已保存')
  })
}

const resetForm = () => {
  syncForm(userInfo.value)
}

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('注销后将返回登录页，当前前端个人信息也会清除。', '确认注销登录', {
      type: 'warning',
      confirmButtonText: '注销',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  logoutLoading.value = true
  try {
    if (userInfo.value.username) {
      await logoutUser(userInfo.value.username)
    }
    userStore.clearToken()
    await router.push('/login')
  } finally {
    logoutLoading.value = false
  }
}

onMounted(async () => {
  if (!userInfo.value.username) {
    await userStore.getUser().catch(() => undefined)
  }
  syncForm(userInfo.value)
})
</script>

<style scoped>
.user-info-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-title h1,
.profile-summary h2,
.panel-header h2 {
  margin: 0;
  color: #1f2937;
}

.page-title h1 {
  font-size: 24px;
  font-weight: 700;
}

.eyebrow {
  margin: 0 0 6px;
  color: #6b7280;
  font-size: 13px;
}

.profile-layout {
  display: grid;
  grid-template-columns: minmax(240px, 320px) 1fr;
  gap: 20px;
  align-items: start;
}

.profile-summary,
.profile-form-panel {
  background: #ffffff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.profile-summary {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px;
}

.profile-avatar {
  background: #2f6fed;
  color: #ffffff;
  font-size: 28px;
  font-weight: 700;
}

.profile-summary p {
  margin: 8px 0 0;
  color: #6b7280;
  word-break: break-all;
}

.profile-form-panel {
  padding: 24px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.panel-header h2,
.profile-summary h2 {
  font-size: 18px;
  font-weight: 700;
}

.profile-form {
  max-width: 560px;
}

.form-actions :deep(.el-form-item__content) {
  display: flex;
  gap: 12px;
}

@media (max-width: 900px) {
  .profile-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page-title,
  .panel-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .profile-form-panel,
  .profile-summary {
    padding: 18px;
  }
}
</style>
