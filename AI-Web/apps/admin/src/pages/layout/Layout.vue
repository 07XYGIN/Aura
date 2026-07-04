<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/modules/user'
import { logout } from '@/api/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const activeAside = computed(() => route.path)
const activeHeader = ref('workspace')

const handleAsideSelect = (index: string) => {
  router.push(index)
}

const handleLogout = async () => {
  const userName: string = userStore.userInfo.username
  try {
    if (userName) {
      await logout(userName)
    }
  } finally {
    userStore.clearToken()
    await router.push('/login')
  }
}
</script>

<template>
  <el-container class="layout-shell">
    <el-aside width="240px" class="layout-aside">
      <div class="brand text-center">Aura Admin</div>
      <el-menu
        :default-active="activeAside"
        class="aside-menu"
        @select="handleAsideSelect"
      >
        <el-menu-item index="/">
          <el-icon><House /></el-icon>
          <span>首页</span>
        </el-menu-item>
        <el-menu-item index="/user/userInfo">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>
        <el-menu-item index="/memory">
          <el-icon><Memo /></el-icon>
          <span>记忆管理</span>
        </el-menu-item>

        <el-divider class="menu-divider" />
        <div class="menu-group-title">Aura 管理</div>

        <el-menu-item index="/aura/profiles">
          <el-icon><UserFilled /></el-icon>
          <span>用户画像</span>
        </el-menu-item>
        <el-menu-item index="/aura/personas">
          <el-icon><Setting /></el-icon>
          <span>人设配置</span>
        </el-menu-item>
        <el-menu-item index="/aura/relationships">
          <el-icon><Connection /></el-icon>
          <span>关系状态</span>
        </el-menu-item>
        <el-menu-item index="/aura/messages">
          <el-icon><ChatDotRound /></el-icon>
          <span>会话消息</span>
        </el-menu-item>
        <el-menu-item index="/aura/emotions">
          <el-icon><DataAnalysis /></el-icon>
          <span>情绪快照</span>
        </el-menu-item>
        <el-menu-item index="/aura/memories">
          <el-icon><Collection /></el-icon>
          <span>长期记忆列表</span>
        </el-menu-item>
        <el-menu-item index="/aura/self-updates">
          <el-icon><EditPen /></el-icon>
          <span>自我更新日志</span>
        </el-menu-item>
        <el-menu-item index="/aura/memory-merge">
          <el-icon><DocumentCopy /></el-icon>
          <span>记忆整理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <el-menu
          mode="horizontal"
          :default-active="activeHeader"
          class="header-menu"
        >
          <el-menu-item index="workspace">工作台</el-menu-item>
        </el-menu>

        <div class="header-actions">
          <el-button @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>

      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout-shell {
  min-height: 100vh;
  background: #f5f7fa;
}

.layout-aside {
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-right: 1px solid #e4e7ed;
}

.brand {
  padding: 24px 20px 16px;
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
  letter-spacing: 0.04em;
}

.aside-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
}

.menu-divider {
  margin: 10px 16px;
}

.menu-group-title {
  padding: 8px 20px;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #ffffff;
  border-bottom: 1px solid #e4e7ed;
}

.header-menu {
  border-bottom: none;
  min-width: 240px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.layout-main {
  padding: 20px;
}
</style>
