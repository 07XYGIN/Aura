import {
  getAuraEmotionSnapshots,
  getAuraLongTermMemories,
  getAuraPersonaConfigs,
  getAuraRelationshipStates,
  getAuraSessionMessages,
  getAuraUserProfiles,
  type AuraEmotionSnapshot,
  type AuraLongTermMemory,
  type AuraPageParams,
  type AuraPageResult,
  type AuraPersonaConfig,
  type AuraRelationshipState,
  type AuraSessionMessage,
  type AuraUserProfile,
} from '@/api/aura'

export interface AuraTableColumn<T extends object> {
  prop: keyof T
  label: string
  minWidth?: number
  width?: number
  type?: 'tag' | 'text' | 'number' | 'tags'
}

export interface AuraResourceConfig<T extends object> {
  eyebrow: string
  title: string
  description: string
  emptyText: string
  columns: AuraTableColumn<T>[]
  fetcher: (params: AuraPageParams) => Promise<{ data?: AuraPageResult<T> }>
}

export const auraUserProfileConfig: AuraResourceConfig<AuraUserProfile> = {
  eyebrow: 'Aura Profile',
  title: '用户画像',
  description: '按用户维度查看 Aura 画像信息。',
  emptyText: '暂无用户画像',
  fetcher: getAuraUserProfiles,
  columns: [
    { prop: 'userId', label: '用户 ID', minWidth: 180, type: 'text' },
    { prop: 'nickname', label: '昵称', minWidth: 160, type: 'tag' },
    { prop: 'gender', label: '性别', width: 100, type: 'text' },
    { prop: 'age', label: '年龄', width: 100, type: 'number' },
    { prop: 'locale', label: '语言', width: 120, type: 'text' },
    { prop: 'timezone', label: '时区', minWidth: 160, type: 'text' },
    { prop: 'updatedAt', label: '更新时间', minWidth: 180, type: 'text' },
  ],
}

export const auraPersonaConfig: AuraResourceConfig<AuraPersonaConfig> = {
  eyebrow: 'Aura Persona',
  title: '人设配置',
  description: '查看 Aura 人设名称、语气、边界和版本信息。',
  emptyText: '暂无人设配置',
  fetcher: getAuraPersonaConfigs,
  columns: [
    { prop: 'userId', label: '用户 ID', minWidth: 180, type: 'text' },
    { prop: 'name', label: '人设名称', minWidth: 160, type: 'tag' },
    { prop: 'tone', label: '语气', minWidth: 180, type: 'text' },
    { prop: 'boundary', label: '边界摘要', minWidth: 260, type: 'text' },
    { prop: 'version', label: '版本', width: 120, type: 'text' },
    { prop: 'updatedAt', label: '更新时间', minWidth: 180, type: 'text' },
  ],
}

export const auraRelationshipConfig: AuraResourceConfig<AuraRelationshipState> = {
  eyebrow: 'Aura Relationship',
  title: '关系状态',
  description: '查看关系阶段、亲密度、信任度与最近互动时间。',
  emptyText: '暂无关系状态',
  fetcher: getAuraRelationshipStates,
  columns: [
    { prop: 'userId', label: '用户 ID', minWidth: 180, type: 'text' },
    { prop: 'stage', label: '关系阶段', minWidth: 160, type: 'tag' },
    { prop: 'affinityScore', label: '亲密度', width: 120, type: 'number' },
    { prop: 'trustScore', label: '信任度', width: 120, type: 'number' },
    { prop: 'lastInteractionAt', label: '最近互动', minWidth: 180, type: 'text' },
    { prop: 'updatedAt', label: '更新时间', minWidth: 180, type: 'text' },
  ],
}

export const auraMessageConfig: AuraResourceConfig<AuraSessionMessage> = {
  eyebrow: 'Aura Messages',
  title: '会话消息',
  description: '按用户或关键字检索会话消息。',
  emptyText: '暂无会话消息',
  fetcher: getAuraSessionMessages,
  columns: [
    { prop: 'sessionId', label: '会话 ID', minWidth: 200, type: 'text' },
    { prop: 'userId', label: '用户 ID', minWidth: 180, type: 'text' },
    { prop: 'role', label: '角色', width: 110, type: 'tag' },
    { prop: 'content', label: '消息内容', minWidth: 360, type: 'text' },
    { prop: 'createdAt', label: '创建时间', minWidth: 180, type: 'text' },
  ],
}

export const auraEmotionConfig: AuraResourceConfig<AuraEmotionSnapshot> = {
  eyebrow: 'Aura Emotion',
  title: '情绪快照',
  description: '查看用户情绪、Aura 心情与置信度快照。',
  emptyText: '暂无情绪快照',
  fetcher: getAuraEmotionSnapshots,
  columns: [
    { prop: 'userId', label: '用户 ID', minWidth: 180, type: 'text' },
    { prop: 'sessionId', label: '会话 ID', minWidth: 200, type: 'text' },
    { prop: 'userEmotion', label: '用户情绪', minWidth: 140, type: 'tag' },
    { prop: 'auraMood', label: 'Aura 心情', minWidth: 140, type: 'tag' },
    { prop: 'confidence', label: '置信度', width: 120, type: 'number' },
    { prop: 'createdAt', label: '创建时间', minWidth: 180, type: 'text' },
  ],
}

export const auraLongTermMemoryConfig: AuraResourceConfig<AuraLongTermMemory> = {
  eyebrow: 'Aura Memory',
  title: '长期记忆列表',
  description: '查看 Aura 长期记忆内容、标签、来源与创建时间。',
  emptyText: '暂无长期记忆',
  fetcher: getAuraLongTermMemories,
  columns: [
    { prop: 'userId', label: '用户 ID', minWidth: 180, type: 'text' },
    { prop: 'title', label: '标题', minWidth: 180, type: 'tag' },
    { prop: 'content', label: '内容', minWidth: 360, type: 'text' },
    { prop: 'tags', label: '标签', minWidth: 180, type: 'tags' },
    { prop: 'source', label: '来源', width: 120, type: 'text' },
    { prop: 'createdAt', label: '创建时间', minWidth: 180, type: 'text' },
  ],
}
