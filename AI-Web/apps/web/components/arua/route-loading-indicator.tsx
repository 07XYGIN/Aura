import { LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Card, CardContent } from '@/components/ui/card'
import type { RouteLoadingIndicatorProps } from '@/types/arua'

export function RouteLoadingIndicator({
  label = 'Loading workspace',
  detail = 'Preparing the next view',
  compact = false,
}: RouteLoadingIndicatorProps) {
  return (
    <Card
      className={cn(
        'rounded-[1.75rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_88%,transparent)] py-0 shadow-[0_28px_70px_-44px_var(--aura-glow)] backdrop-blur-xl',
        compact ? 'w-full max-w-sm' : 'w-full max-w-md',
      )}
    >
      <CardContent className={cn('p-5 sm:p-6', compact ? 'space-y-4' : 'space-y-5')}>
        <div className="flex items-center gap-4">
          <div className="relative flex h-12 w-12 items-center justify-center rounded-[1.2rem] bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-[#23183a] shadow-[0_20px_36px_-24px_var(--aura-glow)]">
            <LoaderCircle className="h-5 w-5 animate-spin" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] tracking-[0.3em] text-[var(--aura-text-soft)] uppercase">
              Route transition
            </p>
            <p className="mt-1 text-base font-semibold text-[var(--aura-text)]">{label}</p>
          </div>
        </div>

        <div className="h-1.5 overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--aura-primary)_12%,var(--aura-surface-strong))]">
          <span className="aura-loading-bar block h-full rounded-full bg-[linear-gradient(90deg,var(--aura-primary),var(--aura-secondary),var(--aura-primary))]" />
        </div>

        <p className="text-sm leading-6 text-[var(--aura-text-muted)]">{detail}</p>
      </CardContent>
    </Card>
  )
}
