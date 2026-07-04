import request from '@/utils/requests'

export interface MemoryMergeParams {
  userId?: string
  threshold?: number
  limit?: number
  scanLimit?: number
}

export interface MemoryMergeMemory {
  id: string
  memory_key: string
  user_id: string
  title?: string
  content: string
  create_time?: string | null
  confidence?: number | null
}

export interface MemoryMergeSimilarity {
  max: number
  min: number
  avg: number
}

export interface MemoryMergeCandidate {
  cluster_id: string
  similarity: MemoryMergeSimilarity
  memory_keys: string[]
  memories: MemoryMergeMemory[]
  suggested_title: string
  suggested_content: string
  suggested_reason: string
}

export interface MemoryMergeCandidateResult {
  items: MemoryMergeCandidate[]
  total: number
  threshold: number
  scanned: number
}

export interface MemoryMergeConfirmPayload {
  userId: string
  memoryKeys: string[]
  mergedTitle: string
  mergedContent: string
  reason?: string
}

export interface MemoryMergeConfirmResult {
  memory_key: string
  merged_from: string[]
  title: string
  content: string
  reason: string
}

export const getMemoryMergeCandidates = (params: MemoryMergeParams) => {
  return request<MemoryMergeCandidateResult>({
    url: '/api/admin/memory-merge/candidates',
    method: 'GET',
    params,
  })
}

export const confirmMemoryMerge = (data: MemoryMergeConfirmPayload) => {
  return request<MemoryMergeConfirmResult>({
    url: '/api/admin/memory-merge/confirm',
    method: 'POST',
    data,
  })
}
