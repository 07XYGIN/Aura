<template>
  <div class="home-page">
    <el-card class="content-card" shadow="never">
      <template #header>首页内容区</template>
      <el-empty description="暂无数据" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useUserStore } from '@/store/modules/user'

const userInfo = useUserStore()

onMounted(() => {
  userInfo.getUser()
})
</script>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.content-card {
  min-height: 320px;
}
</style>
