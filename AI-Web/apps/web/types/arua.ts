import type Link from 'next/link'
import type { ComponentPropsWithoutRef, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

export type AruaNavKey = 'chat' | 'relationship' | 'memories' | 'settings'

export type AruaNavItem = {
  key: AruaNavKey
  label: string
  href: string
  icon: LucideIcon
}

export type SharedUserAccount = {
  name: string
  status: string
  initials: string
  description: string
}

export type AruaShellProps = {
  active: AruaNavKey
  title: ReactNode
  actions?: ReactNode
  children: ReactNode
  contentClassName?: string
  hideHeader?: boolean
  showDefaultAction?: boolean
}

export type RouteLoadingIndicatorProps = {
  label?: string
  detail?: string
  compact?: boolean
}

export type RouteTransitionLinkProps = Omit<ComponentPropsWithoutRef<typeof Link>, 'key'>

export type BrowserSpeechRecognition = {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
}

export type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition

export type SpeechRecognitionEventLike = {
  results: ArrayLike<{
    0: {
      transcript: string
    }
  }>
}

export type ChatMessage = {
  id: string
  sessionId?: string
  role: 'assistant' | 'user'
  content: string
  attachments?: ChatAttachment[]
  pending?: boolean
  createdAt?: string
  turnId?: string
  batchId?: string
  batchIndex?: number
  batchTotal?: number
}

export type ChatAttachment = {
  id?: string
  fileName: string
  contentType?: string
  size?: number
}

export type Live2DPresence = {
  expression: 'calm' | 'warm' | 'playful' | 'thinking' | 'soft' | 'concerned'
  motion: 'idle' | 'acknowledge' | 'wave'
  intensity: number
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
}
