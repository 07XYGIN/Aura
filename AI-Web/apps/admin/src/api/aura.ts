import request from '@/utils/requests'

export interface AuraPageParams {
  userId?: string
  keyword?: string
  page: number
  pageSize: number
}

export interface AuraPageResult<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export interface AuraUserProfile {
  id: string
  userId: string
  nickname?: string
  gender?: string
  age?: number
  locale?: string
  timezone?: string
  updatedAt?: string
}

export interface AuraPersonaConfig {
  id: string
  userId: string
  name?: string
  tone?: string
  boundary?: string
  version?: string
  updatedAt?: string
}

export interface AuraRelationshipState {
  id: string
  userId: string
  stage?: string
  affinityScore?: number
  trustScore?: number
  lastInteractionAt?: string
  updatedAt?: string
}

export interface AuraSessionMessage {
  id: string
  sessionId: string
  userId: string
  role?: string
  content?: string
  isProactive?: boolean
  createdAt?: string
}

export interface AuraEmotionSnapshot {
  id: string
  userId: string
  sessionId?: string
  userEmotion?: string
  auraMood?: string
  confidence?: number
  createdAt?: string
}

export interface AuraLongTermMemory {
  id: string
  userId: string
  title?: string
  content?: string
  tags?: string[]
  source?: string
  createdAt?: string
}

export type AuraResourceKey =
  | 'profiles'
  | 'personas'
  | 'relationships'
  | 'messages'
  | 'emotions'
  | 'memories'

const getAuraResourceList = <T>(resource: AuraResourceKey, params: AuraPageParams) => {
  return request<AuraPageResult<T>>({
    url: `/api/admin/aura/${resource}`,
    method: 'GET',
    params,
  })
}

export const getAuraUserProfiles = (params: AuraPageParams) => {
  return getAuraResourceList<AuraUserProfile>('profiles', params)
}

export const getAuraPersonaConfigs = (params: AuraPageParams) => {
  return getAuraResourceList<AuraPersonaConfig>('personas', params)
}

export const getAuraRelationshipStates = (params: AuraPageParams) => {
  return getAuraResourceList<AuraRelationshipState>('relationships', params)
}

export const getAuraSessionMessages = (params: AuraPageParams) => {
  return getAuraResourceList<AuraSessionMessage>('messages', params)
}

export const getAuraEmotionSnapshots = (params: AuraPageParams) => {
  return getAuraResourceList<AuraEmotionSnapshot>('emotions', params)
}

export const getAuraLongTermMemories = (params: AuraPageParams) => {
  return getAuraResourceList<AuraLongTermMemory>('memories', params)
}
