<template>
  <div class="memory-page">
    <section class="page-title">
      <div>
        <p class="eyebrow">Memory</p>
        <h1>记忆管理</h1>
      </div>

      <el-button type="primary" :loading="loading" @click="loadMemories">
        刷新
      </el-button>
    </section>

    <el-card class="content-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <h2>我的记忆列表</h2>
            <p>当前登录用户在 AI 服务中保存的长期记忆。</p>
          </div>
          <el-tag effect="plain">共 {{ pagination.total }} 条</el-tag>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="memoryList"
        border
        row-key="id"
        empty-text="暂无记忆"
      >
        <el-table-column label="标题" min-width="180">
          <template #default="{ row }">
            <el-tag type="info" effect="plain">
              {{ row.metadata.title || '未命名记忆' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="内容" min-width="360">
          <template #default="{ row }">
            <el-text class="memory-content" line-clamp="3">
              {{ row.metadata.content || row.page_content || '-' }}
            </el-text>
          </template>
        </el-table-column>

        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ row.metadata.create_time || '-' }}
          </template>
        </el-table-column>

        <el-table-column label="记忆 ID" width="260">
          <template #default="{ row }">
            <el-text class="memory-id" truncated>
              {{ row.id }}
            </el-text>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="handlePageSizeChange"
          @current-change="loadMemories"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getMemoryList, type MemoryDocument } from '@/api/memory'

const loading = ref(false)
const memoryList = ref<MemoryDocument[]>([])

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

const loadMemories = async () => {
  loading.value = true
  try {
    const res = await getMemoryList({
      page: pagination.page,
      pageSize: pagination.pageSize,
    })

    memoryList.value = res.data?.items ?? []
    pagination.total = res.data?.total ?? 0
  } catch {
    ElMessage.error('记忆列表加载失败')
  } finally {
    loading.value = false
  }
}

const handlePageSizeChange = () => {
  pagination.page = 1
  loadMemories()
}

onMounted(() => {
  loadMemories()
})
</script>

<style scoped>
.memory-page {
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
.card-header h2 {
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

.content-card {
  min-height: 520px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.card-header h2 {
  font-size: 18px;
  font-weight: 700;
}

.card-header p {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.memory-content {
  color: #374151;
  line-height: 1.7;
}

.memory-id {
  max-width: 220px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding-top: 20px;
}

@media (max-width: 760px) {
  .page-title,
  .card-header,
  .pagination-bar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
