import type { PageResult } from './api'

export type AuraHistoryMessage = {
    id?: string
    role?: 'user' | 'assistant' | 'aura' | 'system'
    senderType?: 'user' | 'assistant' | 'system'
    content?: string
    createdAt?: string
}

export type AuraMemoryMetadata = {
    title?: string
    create_time?: string
    content?: string
    timestamp?: string
    user_id?: string
    [key: string]: unknown
}

export type AuraMemoryItem = {
    id: string
    metadata?: AuraMemoryMetadata
    page_content?: string
    type?: string
}

export type AuraMemoryPage = PageResult<AuraMemoryItem>
