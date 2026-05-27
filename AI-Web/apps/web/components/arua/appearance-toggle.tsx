'use client'

import type { MouseEvent } from 'react'
import { MoonStar, SunMedium } from 'lucide-react'
import { useTheme } from 'next-themes'

type DocumentWithViewTransition = Document & {
  startViewTransition?: (callback: () => void) => {
    finished: Promise<void>
  }
}

export function AppearanceToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const isDark = resolvedTheme !== 'light'

  const handleToggle = (event: MouseEvent<HTMLButtonElement>) => {
    const nextTheme = isDark ? 'light' : 'dark'
    const root = document.documentElement
    const triggerBounds = event.currentTarget.getBoundingClientRect()

    root.style.setProperty('--theme-switch-x', `${triggerBounds.left + triggerBounds.width / 2}px`)
    root.style.setProperty('--theme-switch-y', `${triggerBounds.top + triggerBounds.height / 2}px`)

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const documentWithTransition = document as DocumentWithViewTransition

    if (prefersReducedMotion || !documentWithTransition.startViewTransition) {
      setTheme(nextTheme)
      return
    }

    root.classList.add('theme-transition')

    const transition = documentWithTransition.startViewTransition(() => {
      setTheme(nextTheme)
    })

    transition.finished.finally(() => {
      root.classList.remove('theme-transition')
    })
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      className="group w-full rounded-[1.5rem] border border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface)_76%,transparent)] p-4 text-left transition-all duration-300 hover:border-[var(--aura-border-strong)] hover:shadow-[0_20px_48px_-38px_var(--aura-glow)]"
      aria-label="Toggle appearance"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-base font-semibold text-[var(--aura-text)]">
            {isDark ? 'Dark mode' : 'Light mode'}
          </p>
          <p className="text-sm leading-6 text-[var(--aura-text-muted)]">
            {isDark
              ? 'Deep surfaces with soft highlights for long sessions.'
              : 'Brighter surfaces with the same calm accent palette.'}
          </p>
        </div>

        <div className="relative flex h-12 w-24 shrink-0 items-center rounded-full border border-[var(--aura-border-strong)] bg-[var(--aura-surface-strong)] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
          <SunMedium className="absolute left-3 h-4 w-4 text-[var(--aura-text-soft)]" />
          <MoonStar className="absolute right-3 h-4 w-4 text-[var(--aura-text-soft)]" />
          <span
            className={`absolute top-1 flex h-10 w-10 items-center justify-center rounded-full bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-[#251739] shadow-[0_14px_24px_-16px_var(--aura-glow)] transition-all duration-400 ease-out ${
              isDark ? 'left-[3.25rem]' : 'left-1'
            }`}
          >
            {isDark ? <MoonStar className="h-5 w-5" /> : <SunMedium className="h-5 w-5" />}
          </span>
        </div>
      </div>
    </button>
  )
}
