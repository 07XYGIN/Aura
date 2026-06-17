import { BrainCircuit, MessageSquareText, Settings2 } from 'lucide-react'
import type { AruaNavItem, SharedUserAccount } from '@/types/arua'

export const aruaNavItems: AruaNavItem[] = [
  { key: 'chat', label: 'nav.chat', href: '/', icon: MessageSquareText },
  { key: 'memories', label: 'nav.memories', href: '/memories', icon: BrainCircuit },
  { key: 'settings', label: 'nav.settings', href: '/settings', icon: Settings2 },
]

export const sharedUserAccount: SharedUserAccount = {
  // name: 'account.name',
  // status: 'account.status',
  // initials: 'UA',
  // description: 'account.description',
}
