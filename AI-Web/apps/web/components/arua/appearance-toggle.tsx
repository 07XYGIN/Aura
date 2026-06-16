'use client'

import { MoonStar, SunMedium } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useI18n } from '@/lib/i18n'

export function AppearanceToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const { t } = useI18n()
  const isDark = resolvedTheme !== 'light'

  const handleToggle = () => {
    setTheme(isDark ? 'light' : 'dark')
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      aria-pressed={isDark}
      className="group w-full rounded-[1.5rem] border border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface)_76%,transparent)] p-4 text-left transition-all duration-300 hover:border-[var(--aura-border-strong)] hover:shadow-[0_20px_48px_-38px_var(--aura-glow)]"
      aria-label={t('appearance.toggle')}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-base font-semibold text-[var(--aura-text)]">
            {isDark ? t('appearance.dark') : t('appearance.light')}
          </p>
          <p className="text-sm leading-6 text-[var(--aura-text-muted)]">
            {isDark ? t('appearance.darkDescription') : t('appearance.lightDescription')}
          </p>
        </div>

        <div className="relative flex h-12 w-24 shrink-0 items-center rounded-full border border-[var(--aura-border-strong)] bg-[var(--aura-surface-strong)] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
          <SunMedium className="absolute left-3 h-4 w-4 text-[var(--aura-text-soft)]" />
          <MoonStar className="absolute right-3 h-4 w-4 text-[var(--aura-text-soft)]" />
          <span
            className={`absolute top-1 flex h-10 w-10 items-center justify-center rounded-full bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-[#251739] shadow-[0_14px_24px_-16px_var(--aura-glow)] transition-all duration-300 ease-out ${
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
