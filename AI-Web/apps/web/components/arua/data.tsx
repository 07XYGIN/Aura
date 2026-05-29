import { BrainCircuit, MessageSquareText, Settings2 } from 'lucide-react'
import type { AruaNavItem, SharedUserAccount } from '@/types/arua'

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
