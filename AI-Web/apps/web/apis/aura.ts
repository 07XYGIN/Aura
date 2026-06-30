import request from '@/lib/request'
import type { AuraHistoryMessage, AuraMemoryPage } from '@ai-web/types'

export type { AuraHistoryMessage, AuraMemoryItem, AuraMemoryPage } from '@ai-web/types'

export type AuraMemoryRetention = {
  plan: 'free' | 'permanent'
  permanent: boolean
  daysRemaining: number | null
  shouldPrompt: boolean
  paywall: boolean
}

export type AuraEmotionReportPreview = {
  eligible: boolean
  chatTurns: number
  roundsRemaining: number
  reportId?: string
  status?: 'preview' | 'paid'
  priceCents?: number
  previewKeywords?: string
  previewText?: string
  fullReport?: string
}

export type AuraEmotionInsightReport = {
  id: string
  userId: string
  status: 'preview' | 'paid'
  priceCents: number
  previewKeywords: string
  previewText: string
  fullReport: string
  paidAt?: string
  createdAt?: string
  updatedAt?: string
}

export type AuraUploadAttachmentInput = {
  fileName: string
  contentType: string
  size: number
  dataBase64: string
}

export type AuraUploadedAttachment = {
  id: string
  fileName: string
  contentType?: string
  size?: number
  summary?: string
  createdAt?: string
}

export type AuraCityAdcode = {
  adcode: string
  province?: string
  city?: string
  district?: string
  citycode?: string
  source: 'regeo' | 'district' | 'ip'
}

export const aura = {
  uploadAttachments: (files: AuraUploadAttachmentInput[]) =>
    request<{ items: AuraUploadedAttachment[] }>('/api/chat/attachments', {
      method: 'POST',
      body: { files },
    }),
  resolveCityAdcode: (params: { city?: string; longitude?: number; latitude?: number } = {}) => {
    const query = new URLSearchParams()

    if (params.city) {
      query.set('city', params.city)
    }
    if (typeof params.longitude === 'number') {
      query.set('longitude', String(params.longitude))
    }
    if (typeof params.latitude === 'number') {
      query.set('latitude', String(params.latitude))
    }

    const suffix = query.toString() ? `?${query.toString()}` : ''

    return request<AuraCityAdcode>(`/api/location/adcode${suffix}`, {
      method: 'GET',
    })
  },
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
  getMemories: (page = 1, pageSize = 20, scope: 'long' | 'mid' | 'all' = 'long') =>
    request<AuraMemoryPage>(`/api/aura/memories?page=${page}&pageSize=${pageSize}&scope=${scope}`, {
      method: 'GET',
    }),
  getMemoryRetention: () =>
    request<AuraMemoryRetention>('/api/aura/memories/retention', {
      method: 'GET',
    }),
  deleteMemory: (memoryId: string) =>
    request<{ deleted: boolean; memoryId: string }>(
      `/api/aura/memories/${encodeURIComponent(memoryId)}`,
      {
        method: 'DELETE',
      },
    ),
  clearMemories: (scope: 'long' | 'mid' | 'all' = 'all') =>
    request<{ deletedCount: number }>(`/api/aura/memories?scope=${scope}`, {
      method: 'DELETE',
    }),
  submitConversationFeedback: (payload: {
    sessionId: string
    score: number
    comment?: string
  }) =>
    request('/api/aura/conversation-feedback', {
      method: 'POST',
      body: payload,
    }),
  recordBehaviorEvent: (payload: {
    sessionId?: string
    messageId?: string
    eventType: string
    metadata?: string
  }) =>
    request('/api/aura/behavior-events', {
      method: 'POST',
      body: payload,
    }),
  purchaseEmotionReport: (reportId: string) =>
    request<AuraEmotionInsightReport>(
      `/api/aura/emotion-report/${encodeURIComponent(reportId)}/purchase`,
      {
        method: 'POST',
      },
    ),
}
