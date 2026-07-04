<template>
  <div class="memory-merge-page">
    <section class="page-title">
      <div>
        <p class="eyebrow">Aura Memory Merge</p>
        <h1>记忆整理</h1>
        <p class="description">
          扫描同一用户的长期记忆相似簇，确认后写入合并记忆，并把原条目标记为已被替代。
        </p>
      </div>
      <el-button :loading="loading" @click="loadCandidates">刷新</el-button>
    </section>

    <el-card class="filter-card" shadow="never">
      <el-form :model="filters" class="filter-form" label-width="92px">
        <el-form-item label="用户 ID">
          <el-input v-model="filters.userId" clearable placeholder="不填则使用当前登录用户" />
        </el-form-item>
        <el-form-item label="相似阈值">
          <el-input-number
            v-model="filters.threshold"
            :min="0.5"
            :max="0.99"
            :step="0.01"
            :precision="2"
          />
        </el-form-item>
        <el-form-item label="扫描数量">
          <el-input-number v-model="filters.scanLimit" :min="20" :max="1000" :step="20" />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button type="primary" :loading="loading" @click="loadCandidates">扫描相似记忆</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="result-card" shadow="never">
      <template #header>
        <div class="card-header">
          <h2>候选合并簇</h2>
          <div class="summary-tags">
            <el-tag effect="plain">候选 {{ result.total }} 组</el-tag>
            <el-tag effect="plain">已扫描 {{ result.scanned }} 条</el-tag>
            <el-tag effect="plain">阈值 {{ result.threshold.toFixed(2) }}</el-tag>
          </div>
        </div>
      </template>

      <el-empty v-if="!loading && candidates.length === 0" description="暂无可合并的相似记忆" />

      <div v-else v-loading="loading" class="candidate-list">
        <section v-for="candidate in candidates" :key="candidate.cluster_id" class="candidate-panel">
          <div class="candidate-header">
            <div>
              <h3>{{ candidate.draftTitle }}</h3>
              <p>
                {{ candidate.memories.length }} 条记忆，
                最高相似度 {{ candidate.similarity.max.toFixed(2) }}，
                平均 {{ candidate.similarity.avg.toFixed(2) }}
              </p>
            </div>
            <el-tag type="warning" effect="plain">人工确认后生效</el-tag>
          </div>

          <div class="memory-list">
            <article v-for="memory in candidate.memories" :key="memory.memory_key" class="memory-row">
              <div class="memory-meta">
                <el-tag effect="plain">{{ memory.title || '未命名记忆' }}</el-tag>
                <span>{{ formatDate(memory.create_time) }}</span>
                <span v-if="memory.confidence !== null && memory.confidence !== undefined">
                  置信度 {{ Number(memory.confidence).toFixed(2) }}
                </span>
              </div>
              <p>{{ memory.content }}</p>
              <code>{{ memory.memory_key }}</code>
            </article>
          </div>

          <el-form label-width="92px" class="merge-form">
            <el-form-item label="合并标题">
              <el-input v-model="candidate.draftTitle" maxlength="80" show-word-limit />
            </el-form-item>
            <el-form-item label="合并内容">
              <el-input
                v-model="candidate.draftContent"
                type="textarea"
                :rows="4"
                maxlength="320"
                show-word-limit
              />
            </el-form-item>
            <el-form-item label="合并原因">
              <el-input v-model="candidate.draftReason" maxlength="160" show-word-limit />
            </el-form-item>
            <el-form-item class="merge-actions">
              <el-button
                type="primary"
                :loading="confirmingId === candidate.cluster_id"
                @click="confirmMerge(candidate)"
              >
                确认合并
              </el-button>
              <el-button @click="restoreSuggestion(candidate)">恢复建议</el-button>
            </el-form-item>
          </el-form>
        </section>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  confirmMemoryMerge,
  getMemoryMergeCandidates,
  type MemoryMergeCandidate,
  type MemoryMergeCandidateResult,
} from '@/api/memoryMerge'

type EditableCandidate = MemoryMergeCandidate & {
  draftTitle: string
  draftContent: string
  draftReason: string
}

const loading = ref(false)
const confirmingId = ref('')
const candidates = ref<EditableCandidate[]>([])
const result = reactive<MemoryMergeCandidateResult>({
  items: [],
  total: 0,
  threshold: 0.85,
  scanned: 0,
})

const filters = reactive({
  userId: '',
  threshold: 0.85,
  scanLimit: 300,
})

const toEditableCandidate = (candidate: MemoryMergeCandidate): EditableCandidate => ({
  ...candidate,
  draftTitle: candidate.suggested_title,
  draftContent: candidate.suggested_content,
  draftReason: candidate.suggested_reason,
})

const loadCandidates = async () => {
  loading.value = true
  try {
    const res = await getMemoryMergeCandidates({
      userId: filters.userId.trim() || undefined,
      threshold: filters.threshold,
      scanLimit: filters.scanLimit,
      limit: 20,
    })
    const data = res.data
    result.items = data?.items ?? []
    result.total = data?.total ?? 0
    result.threshold = data?.threshold ?? filters.threshold
    result.scanned = data?.scanned ?? 0
    candidates.value = result.items.map(toEditableCandidate)
  } catch {
    ElMessage.error('相似记忆扫描失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.userId = ''
  filters.threshold = 0.85
  filters.scanLimit = 300
  loadCandidates()
}

const restoreSuggestion = (candidate: EditableCandidate) => {
  candidate.draftTitle = candidate.suggested_title
  candidate.draftContent = candidate.suggested_content
  candidate.draftReason = candidate.suggested_reason
}

const confirmMerge = async (candidate: EditableCandidate) => {
  const title = candidate.draftTitle.trim()
  const content = candidate.draftContent.trim()
  const userId = candidate.memories[0]?.user_id || filters.userId.trim()

  if (!userId) {
    ElMessage.warning('缺少用户 ID，不能合并')
    return
  }
  if (!title || !content) {
    ElMessage.warning('合并标题和内容不能为空')
    return
  }

  await ElMessageBox.confirm(
    `确认把这 ${candidate.memory_keys.length} 条长期记忆合并为一条吗？原记忆会标记为已替代。`,
    '确认合并记忆',
    {
      type: 'warning',
      confirmButtonText: '确认合并',
      cancelButtonText: '取消',
    },
  )

  confirmingId.value = candidate.cluster_id
  try {
    await confirmMemoryMerge({
      userId,
      memoryKeys: candidate.memory_keys,
      mergedTitle: title,
      mergedContent: content,
      reason: candidate.draftReason.trim() || 'admin_memory_merge',
    })
    ElMessage.success('记忆已合并')
    await loadCandidates()
  } catch {
    ElMessage.error('记忆合并失败')
  } finally {
    confirmingId.value = ''
  }
}

const formatDate = (value: string | null | undefined) => {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.memory-merge-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-title,
.card-header,
.summary-tags,
.candidate-header,
.memory-meta {
  display: flex;
  align-items: center;
}

.page-title,
.card-header,
.candidate-header {
  justify-content: space-between;
  gap: 16px;
}

.page-title h1,
.card-header h2,
.candidate-header h3 {
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

.description,
.candidate-header p {
  margin: 8px 0 0;
  color: #4b5563;
  font-size: 14px;
  line-height: 1.7;
}

.filter-card,
.result-card {
  border-radius: 8px;
}

.filter-form {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 220px 220px auto;
  gap: 12px 16px;
}

.filter-form :deep(.el-form-item),
.merge-form :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.filter-actions :deep(.el-form-item__content),
.merge-actions :deep(.el-form-item__content) {
  display: flex;
  gap: 10px;
}

.summary-tags,
.memory-meta {
  gap: 8px;
  flex-wrap: wrap;
}

.candidate-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 220px;
}

.candidate-panel {
  padding: 18px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #ffffff;
}

.memory-list {
  display: grid;
  gap: 10px;
  margin: 16px 0;
}

.memory-row {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
}

.memory-row p {
  margin: 8px 0;
  color: #374151;
  line-height: 1.7;
}

.memory-row code {
  color: #6b7280;
  font-size: 12px;
  word-break: break-all;
}

.memory-meta span {
  color: #6b7280;
  font-size: 13px;
}

.merge-form {
  max-width: 980px;
}

@media (max-width: 1180px) {
  .filter-form {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }
}

@media (max-width: 760px) {
  .page-title,
  .card-header,
  .candidate-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .filter-form {
    grid-template-columns: 1fr;
  }
}
</style>
