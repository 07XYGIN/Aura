import { getCurrentUserId } from '@/lib/current-user'
import pythonRequest from '@/lib/python-request'
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

const requireCurrentUserId = () => {
  const userId = getCurrentUserId()
  if (!userId) {
    throw new Error('Missing user id')
  }
  return userId
}

export const aura = {
  uploadAttachments: (files: AuraUploadAttachmentInput[]) =>
    pythonRequest<{ items: AuraUploadedAttachment[] }>('/api/attachments', {
      method: 'POST',
      body: { userId: requireCurrentUserId(), files },
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

    return pythonRequest<AuraCityAdcode>(`/api/location/adcode${suffix}`, {
      method: 'GET',
    })
  },
  getCurrentMessages: () =>
    pythonRequest<AuraHistoryMessage[]>(`/api/history/${encodeURIComponent(requireCurrentUserId())}`, {
      method: 'GET',
    }),
  deleteCurrentMessage: (messageId: string) =>
    pythonRequest<{ deleted: boolean; messageId: string }>(
      `/api/history/${encodeURIComponent(requireCurrentUserId())}/messages/${encodeURIComponent(messageId)}`,
      {
        method: 'DELETE',
      },
    ),
  clearCurrentMessages: () =>
    pythonRequest<{ deletedCount: number }>(`/api/history/${encodeURIComponent(requireCurrentUserId())}`, {
      method: 'DELETE',
    }),
  getMemories: (
    page = 1,
    pageSize = 20,
    scope: 'long' | 'mid' | 'all' = 'long',
    includeInactive = false,
  ) =>
    pythonRequest<AuraMemoryPage>(
      `/api/memory/list?userId=${encodeURIComponent(requireCurrentUserId())}&page=${page}&pageSize=${pageSize}&scope=${scope}&includeInactive=${includeInactive}`,
      {
        method: 'GET',
      },
    ),
  getMemoryRetention: () =>
    pythonRequest<AuraMemoryRetention>(
      `/api/memory/retention?userId=${encodeURIComponent(requireCurrentUserId())}`,
      {
        method: 'GET',
      },
    ),
  deleteMemory: (memoryId: string) =>
    pythonRequest<{ deleted: boolean; memoryId: string }>(
      `/api/memory/${encodeURIComponent(memoryId)}?userId=${encodeURIComponent(requireCurrentUserId())}`,
      {
        method: 'DELETE',
      },
    ),
  clearMemories: (scope: 'long' | 'mid' | 'all' = 'all') =>
    pythonRequest<{ deletedCount: number }>(
      `/api/memory/list?userId=${encodeURIComponent(requireCurrentUserId())}&scope=${scope}`,
      {
        method: 'DELETE',
      },
    ),
  submitConversationFeedback: (payload: {
    sessionId: string
    score: number
    comment?: string
  }) =>
    pythonRequest('/api/aura/conversation-feedback', {
      method: 'POST',
      body: { ...payload, userId: requireCurrentUserId() },
    }),
  recordBehaviorEvent: (payload: {
    sessionId?: string
    messageId?: string
    eventType: string
    metadata?: string
  }) =>
    pythonRequest('/api/aura/behavior-events', {
      method: 'POST',
      body: { ...payload, userId: requireCurrentUserId() },
    }),
  purchaseEmotionReport: (reportId: string) =>
    pythonRequest<AuraEmotionInsightReport>(
      `/api/aura/emotion-report/${encodeURIComponent(reportId)}/purchase`,
      {
        method: 'POST',
        body: { userId: requireCurrentUserId() },
      },
    ),
}
