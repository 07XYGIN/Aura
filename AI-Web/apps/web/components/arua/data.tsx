import type { LucideIcon } from 'lucide-react'
import { BrainCircuit, MessageSquareText, Settings2 } from 'lucide-react'

export type AruaNavKey = 'chat' | 'memories' | 'settings'

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

export const aruaNavItems: AruaNavItem[] = [
  { key: 'chat', label: 'AI Chat', href: '/', icon: MessageSquareText },
  { key: 'memories', label: 'Memories', href: '/memories', icon: BrainCircuit },
  { key: 'settings', label: 'Settings', href: '/settings', icon: Settings2 },
]

export const sharedUserAccount: SharedUserAccount = {
  name: 'User Account',
  status: 'Awaiting backend sync',
  initials: 'UA',
  description:
    'Profile details, preferences, and companion permissions will appear here after the account service is connected.',
}
