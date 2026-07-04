<template>
  <div class="self-updates-page">
    <section class="page-title">
      <div>
        <p class="eyebrow">Aura Changelog</p>
        <h1>自我更新日志</h1>
        <p class="description">记录小乔最近给 Aura 做过的变化，未回应的记录会进入对话上下文。</p>
      </div>
      <el-button :loading="loading" @click="loadUpdates">刷新</el-button>
    </section>

    <el-card class="form-card" shadow="never">
      <template #header>
        <div class="card-header">
          <h2>{{ editingId ? '编辑更新' : '快速录入' }}</h2>
          <el-tag effect="plain">30 秒内记一笔</el-tag>
        </div>
      </template>

      <el-form :model="form" label-width="88px" class="entry-form">
        <el-form-item label="标题">
          <el-input
            v-model="form.title"
            type="textarea"
            :rows="3"
            maxlength="160"
            show-word-limit
            placeholder="比如：给你加了时间感知，因为你之前老是感觉不到我们隔了多久没聊"
          />
        </el-form-item>

        <div class="form-grid">
          <el-form-item label="分类">
            <el-select
              v-model="form.category"
              filterable
              allow-create
              default-first-option
              placeholder="选择或输入分类"
            >
              <el-option v-for="item in categories" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>

          <el-form-item label="时间">
            <el-date-picker
              v-model="form.occurredAt"
              type="datetime"
              placeholder="选择发生时间"
              format="YYYY-MM-DD HH:mm"
            />
          </el-form-item>
        </div>

        <el-collapse class="detail-collapse">
          <el-collapse-item title="可选详情" name="detail">
            <el-input
              v-model="form.detail"
              type="textarea"
              :rows="4"
              placeholder="补充背景，不填也可以"
            />
          </el-collapse-item>
        </el-collapse>

        <el-form-item class="form-actions">
          <el-button type="primary" :loading="saving" @click="handleSubmit">
            {{ editingId ? '保存修改' : '提交' }}
          </el-button>
          <el-button @click="resetForm">清空</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="list-card" shadow="never">
      <template #header>
        <div class="card-header">
          <h2>最近记录</h2>
          <div class="list-tools">
            <el-select v-model="reactedFilter" class="status-filter" @change="loadUpdates">
              <el-option label="全部" value="all" />
              <el-option label="未回应" value="false" />
              <el-option label="已回应" value="true" />
            </el-select>
            <el-tag effect="plain">共 {{ total }} 条</el-tag>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="updates" row-key="id" border>
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">
            <span>{{ formatDate(row.occurred_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="分类" width="130">
          <template #default="{ row }">
            <el-tag effect="plain">{{ row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="360">
          <template #default="{ row }">
            <div class="title-cell">
              <strong>{{ row.title }}</strong>
              <p v-if="row.detail">{{ row.detail }}</p>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.reacted ? 'success' : 'warning'" effect="plain">
              {{ row.reacted ? '已回应' : '未回应' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="startEdit(row)">编辑</el-button>
              <el-button v-if="row.reacted" link type="warning" @click="resetReaction(row)">重置</el-button>
              <el-button link type="danger" @click="removeUpdate(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createSelfUpdate,
  deleteSelfUpdate,
  getSelfUpdates,
  updateSelfUpdate,
  type SelfUpdateItem,
} from '@/api/selfUpdates'

const categories = ['memory', 'perception', 'personality', 'infra']
const updates = ref<SelfUpdateItem[]>([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const reactedFilter = ref<'all' | 'true' | 'false'>('all')

const form = reactive({
  title: '',
  detail: '',
  category: 'infra',
  occurredAt: new Date(),
})

const normalizeDate = (value: Date | string | null | undefined) => {
  const date = value instanceof Date ? value : value ? new Date(value) : new Date()
  return date.toISOString()
}

const loadUpdates = async () => {
  loading.value = true
  try {
    const res = await getSelfUpdates({
      reacted: reactedFilter.value === 'all' ? undefined : reactedFilter.value === 'true',
      limit: 100,
      order: 'desc',
    })
    updates.value = res.data?.items ?? []
    total.value = res.data?.total ?? 0
  } catch {
    ElMessage.error('更新日志加载失败')
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  editingId.value = null
  form.title = ''
  form.detail = ''
  form.category = 'infra'
  form.occurredAt = new Date()
}

const handleSubmit = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('先写一句更新标题')
    return
  }

  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      detail: form.detail.trim() || null,
      category: form.category.trim() || 'infra',
      occurred_at: normalizeDate(form.occurredAt),
    }

    if (editingId.value) {
      await updateSelfUpdate(editingId.value, payload)
      ElMessage.success('已保存修改')
    } else {
      await createSelfUpdate(payload)
      ElMessage.success('已录入')
    }

    resetForm()
    await loadUpdates()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const startEdit = (item: SelfUpdateItem) => {
  editingId.value = item.id
  form.title = item.title
  form.detail = item.detail ?? ''
  form.category = item.category || 'infra'
  form.occurredAt = item.occurred_at ? new Date(item.occurred_at) : new Date()
}

const resetReaction = async (item: SelfUpdateItem) => {
  await updateSelfUpdate(item.id, { reacted: false })
  ElMessage.success('已重置为未回应')
  await loadUpdates()
}

const removeUpdate = async (item: SelfUpdateItem) => {
  await ElMessageBox.confirm('删除后不会保留软删除记录，确定删除吗？', '删除更新日志', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await deleteSelfUpdate(item.id)
  ElMessage.success('已删除')
  await loadUpdates()
}

const formatDate = (value: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  loadUpdates()
})
</script>

<style scoped>
.self-updates-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-title,
.card-header,
.list-tools,
.row-actions {
  display: flex;
  align-items: center;
}

.page-title,
.card-header {
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
}

.form-card,
.list-card {
  border-radius: 8px;
}

.entry-form {
  max-width: 980px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 16px;
}

.form-grid :deep(.el-form-item) {
  margin-bottom: 18px;
}

.detail-collapse {
  margin: 4px 0 18px;
  border-top: none;
}

.form-actions :deep(.el-form-item__content) {
  display: flex;
  gap: 10px;
}

.list-tools {
  gap: 12px;
}

.status-filter {
  width: 120px;
}

.title-cell {
  line-height: 1.6;
}

.title-cell p {
  margin: 4px 0 0;
  color: #6b7280;
}

.row-actions {
  gap: 8px;
}

@media (max-width: 760px) {
  .page-title,
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
