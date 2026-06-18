import request from '@/lib/request'
import type { AuraHistoryMessage, AuraMemoryPage } from '@ai-web/types'

export type { AuraHistoryMessage, AuraMemoryItem, AuraMemoryPage } from '@ai-web/types'

export const aura = {
  getCurrentMessages: () =>
    request<AuraHistoryMessage[]>('/api/aura/sessions/current/messages', {
      method: 'GET',
    }),
  deleteCurrentMessage: (messageId: string) =>
    request<{ deleted: boolean; messageId: string }>(
      `/api/aura/sessions/current/messages/${encodeURIComponent(messageId)}`,
      {
        method: 'DELETE',
      },
    ),
  clearCurrentMessages: () =>
    request<{ deletedCount: number }>('/api/aura/sessions/current/messages', {
      method: 'DELETE',
    }),
  getMemories: (page = 1, pageSize = 20) =>
    request<AuraMemoryPage>(`/api/aura/memories?page=${page}&pageSize=${pageSize}`, {
      method: 'GET',
    }),
  deleteMemory: (memoryId: string) =>
    request<{ deleted: boolean; memoryId: string }>(
      `/api/aura/memories/${encodeURIComponent(memoryId)}`,
      {
        method: 'DELETE',
      },
    ),
  clearMemories: () =>
    request<{ deletedCount: number }>('/api/aura/memories', {
      method: 'DELETE',
    }),
}
