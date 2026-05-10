<template>
  <div class="home-page">
    <el-row :gutter="20">

    </el-row>

    <el-card class="content-card" shadow="never">
      <template #header>首页内容区</template>
      <el-empty description="这里是右侧主内容区域，可继续接入业务模块" />
    </el-card>
  </div>
</template>
<script setup lang="ts">
import {useUserStore} from "@/store/modules/user.ts";
import {onMounted} from "vue";
const userInfo = useUserStore();

onMounted(() => {
  userInfo.getUser();
});
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
