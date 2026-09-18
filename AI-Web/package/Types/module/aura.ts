import type { PageResult } from './api'

export type AuraChatAttachment = {
    id?: string
    fileName: string
    contentType?: string
    size?: number
}

export type AuraHistoryMessage = {
    id?: string
    sessionId?: string
    role?: 'user' | 'assistant' | 'aura' | 'system'
    senderType?: 'user' | 'assistant' | 'system'
    content?: string
    attachments?: AuraChatAttachment[] | string[]
    createdAt?: string
    turnId?: string
    batchId?: string
    batchIndex?: number
    batchTotal?: number
    isProactive?: boolean
}

export type AuraMemoryMetadata = {
    title?: string
    create_time?: string
    content?: string
    timestamp?: string
    user_id?: string
    memory_key?: string
    memory_scope?: 'long' | 'mid' | string
    status?: 'active' | 'superseded' | string
    supersedes?: string
    superseded_by?: string
    recall_count?: number
    promoted_to_long?: boolean
    promoted_memory_key?: string
    promoted_from_mid_key?: string
    promoted_at?: string
    [key: string]: unknown
}

export type AuraMemoryItem = {
    id: string
    memory_key?: string
    status?: string
    supersedes?: string
    superseded_by?: string
    promoted_to_long?: boolean
    promoted_memory_key?: string
    is_retrievable?: boolean
    metadata?: AuraMemoryMetadata
    page_content?: string
    type?: string
}

export type AuraMemoryPage = PageResult<AuraMemoryItem>

export type AuraSSEEventType =
    | 'turn.started'
    | 'message.created'
    | 'emotion.updated'
    | 'memory.referenced'
    | 'memory.candidate'
    | 'relationship.updated'
    | 'presence.updated'
    | 'activity.updated'
    | 'approval.required'
    | 'conversation.branched'
    | 'turn.completed'
    | 'error'

export type AuraSSEEventV1 = {
    version: 1
    eventId: string
    turnId: string
    sequence: number
    type: AuraSSEEventType
    timestamp: string
    payload: Record<string, unknown>
    /** Legacy discriminator kept during the v0 compatibility window. */
    event?: string
    legacyType?: string
    content?: string
    presence?: Record<string, unknown>
    messageId?: string
    batchId?: string
    batchIndex?: number
    batchTotal?: number
    delayMs?: number
    sentAt?: string
}
