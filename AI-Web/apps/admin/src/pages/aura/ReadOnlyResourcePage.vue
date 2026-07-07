<template>
  <div class="aura-resource-page">
    <section class="page-title">
      <div>
        <p class="eyebrow">{{ config.eyebrow }}</p>
        <h1>{{ config.title }}</h1>
        <p class="description">{{ config.description }}</p>
      </div>

    </section>

    <el-card class="filter-card" shadow="never">
      <el-form :model="filters" class="filter-form" label-width="72px">
        <el-form-item label="用户 ID">
          <el-input v-model="filters.userId" clearable placeholder="按用户 ID 查询" />
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="filters.keyword" clearable placeholder="按关键字查询" />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button type="primary" :loading="loading" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-button :loading="loading" @click="loadData">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="content-card" shadow="never">
      <template #header>
        <div class="card-header">
          <h2>{{ config.title }}</h2>
          <el-tag effect="plain">共 {{ pagination.total }} 条</el-tag>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="rows"
        border
        row-key="id"
        :empty-text="config.emptyText"
      >
        <el-table-column
          v-for="column in config.columns"
          :key="String(column.prop)"
          :label="column.label"
          :min-width="column.minWidth"
          :width="column.width"
        >
          <template #default="{ row }">
            <template v-if="column.type === 'tag'">
              <el-tag effect="plain">{{ formatValue(getCellValue(row, column.prop)) }}</el-tag>
            </template>
            <template v-else-if="column.type === 'tags'">
              <div class="tag-list">
                <el-tag
                  v-for="tag in normalizeTags(getCellValue(row, column.prop))"
                  :key="tag"
                  type="info"
                  effect="plain"
                >
                  {{ tag }}
                </el-tag>
                <span v-if="normalizeTags(getCellValue(row, column.prop)).length === 0">-</span>
              </div>
            </template>
            <template v-else>
              <el-text class="cell-text" line-clamp="2">
                {{ formatValue(getCellValue(row, column.prop)) }}
              </el-text>
            </template>
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
          @current-change="loadData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts" generic="T extends object">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { AuraResourceConfig } from './resourceConfig'

const props = defineProps<{
  config: AuraResourceConfig<T>
}>()

const loading = ref(false)
const rows = ref<T[]>([])

const filters = reactive({
  userId: '',
  keyword: '',
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

const formatValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2)
  return String(value)
}

const normalizeTags = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean)
  }

  if (typeof value === 'string' && value.startsWith('[')) {
    try {
      const parsed = JSON.parse(value) as unknown
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item)).filter(Boolean)
      }
    } catch {
      return []
    }
  }

  return []
}

const getCellValue = (row: T, prop: keyof T) => {
  return row[prop]
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await props.config.fetcher({
      userId: filters.userId || undefined,
      keyword: filters.keyword || undefined,
      page: pagination.page,
      pageSize: pagination.pageSize,
    })

    rows.value = res.data?.items ?? []
    pagination.total = res.data?.total ?? 0
  } catch {
    ElMessage.error(`${props.config.title}加载失败`)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadData()
}

const handleReset = () => {
  filters.userId = ''
  filters.keyword = ''
  pagination.page = 1
  loadData()
}

const handlePageSizeChange = () => {
  pagination.page = 1
  loadData()
}

watch(
  () => props.config,
  () => {
    rows.value = []
    filters.userId = ''
    filters.keyword = ''
    pagination.page = 1
    pagination.total = 0
    loadData()
  },
)

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.aura-resource-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-title {
  display: flex;
  align-items: flex-start;
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

.description {
  margin: 8px 0 0;
  color: #4b5563;
  font-size: 14px;
  line-height: 1.7;
}

.filter-card,
.content-card {
  border-radius: 8px;
}

.filter-form {
  display: grid;
  grid-template-columns: repeat(3, minmax(180px, 1fr));
  gap: 12px 16px;
}

.filter-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.filter-actions :deep(.el-form-item__content) {
  display: flex;
  gap: 10px;
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

.cell-text {
  color: #374151;
  line-height: 1.6;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding-top: 20px;
}

@media (max-width: 980px) {
  .filter-form {
    grid-template-columns: 1fr;
  }
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
