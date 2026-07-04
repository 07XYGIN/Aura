import request from '@/utils/requests'

export interface SelfUpdateItem {
  id: string
  occurred_at: string
  change_date: string
  title: string
  detail?: string | null
  category: string
  reacted: boolean
  reacted_at?: string | null
  metadata?: Record<string, unknown>
  created_at?: string | null
  updated_at?: string | null
}

export interface SelfUpdateListResult {
  items: SelfUpdateItem[]
  total: number
  limit: number
}

export interface SelfUpdatePayload {
  occurred_at?: string
  title?: string
  detail?: string | null
  category?: string
  reacted?: boolean
  metadata?: Record<string, unknown>
}

export const getSelfUpdates = (params: { reacted?: boolean; limit?: number; order?: 'asc' | 'desc' }) => {
  return request<SelfUpdateListResult>({
    url: '/api/admin/self-updates',
    method: 'GET',
    params,
  })
}

export const createSelfUpdate = (data: SelfUpdatePayload) => {
  return request<SelfUpdateItem>({
    url: '/api/admin/self-updates',
    method: 'POST',
    data,
  })
}

export const updateSelfUpdate = (id: string, data: SelfUpdatePayload) => {
  return request<SelfUpdateItem>({
    url: `/api/admin/self-updates/${id}`,
    method: 'PATCH',
    data,
  })
}

export const deleteSelfUpdate = (id: string) => {
  return request<{ deleted: boolean; id: string }>({
    url: `/api/admin/self-updates/${id}`,
    method: 'DELETE',
  })
}
