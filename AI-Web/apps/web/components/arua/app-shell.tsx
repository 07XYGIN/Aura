import { ViewTransition } from 'react'
import type { ReactNode } from 'react'
import { CircleUserRound } from 'lucide-react'
import { cn } from '@/lib/utils'
import { aruaNavItems, sharedUserAccount, type AruaNavKey } from '@/components/arua/data'
import { RouteTransitionLink } from '@/components/arua/route-transition-link'

type AruaShellProps = {
  active: AruaNavKey
  title: ReactNode
  actions?: ReactNode
  children: ReactNode
  contentClassName?: string
  showDefaultAction?: boolean
}

export function AruaAppShell({
  active,
  title,
  actions,
  children,
  contentClassName,
  showDefaultAction = true,
}: AruaShellProps) {
  const activeIndex = aruaNavItems.findIndex((item) => item.key === active)

  return (
    <div className="relative min-h-screen bg-[var(--aura-bg)] text-[var(--aura-text)]">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-[-10rem] top-[-8rem] h-72 w-72 rounded-full bg-[var(--aura-gradient-start)] blur-3xl" />
        <div className="absolute bottom-[-12rem] right-[-8rem] h-80 w-80 rounded-full bg-[var(--aura-gradient-end)] blur-3xl" />
        <div className="absolute left-1/3 top-24 h-56 w-56 rounded-full bg-[color-mix(in_srgb,var(--aura-primary)_12%,transparent)] blur-3xl" />
      </div>

      <div className="relative flex min-h-screen flex-col lg:block">
        <aside
          className="border-b border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_90%,transparent)] px-4 py-5 backdrop-blur-xl lg:fixed lg:inset-y-0 lg:w-80 lg:border-b-0 lg:border-r lg:px-6 lg:py-7"
          style={{ viewTransitionName: 'aura-sidebar' }}
        >
          <div className="flex h-full flex-col">
            <div className="aura-panel rounded-[2rem] px-5 py-6 shadow-[0_24px_64px_-48px_var(--aura-glow)]">
              <p className="text-xs uppercase tracking-[0.36em] text-[var(--aura-text-soft)]">
                Companion console
              </p>
              <div className="mt-3 space-y-1">
                <h1 className="text-3xl font-bold tracking-tight text-[var(--aura-primary)]">
                  Arua
                </h1>
                <p className="text-sm leading-7 text-[var(--aura-text-muted)]">
                  A calm AI workspace for conversation, memory, and personal tuning.
                </p>
              </div>
            </div>

            <div className="mt-6 px-1">
              <p className="text-xs uppercase tracking-[0.32em] text-[var(--aura-text-soft)]">
                Navigate
              </p>
            </div>

            <nav className="aura-scrollbar mt-4 grid grid-cols-3 gap-3 overflow-x-auto pb-1 lg:grid-cols-1 lg:pb-0">
              {aruaNavItems.map((item, index) => {
                const Icon = item.icon
                const isActive = item.key === active
                const transitionTypes =
                  index > activeIndex ? ['nav-forward'] : index < activeIndex ? ['nav-back'] : []

                return (
                  <RouteTransitionLink
                    key={item.key}
                    href={item.href}
                    transitionTypes={transitionTypes}
                    className={cn(
                      'group flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition-all duration-200 hover:-translate-y-0.5 lg:text-base',
                      isActive
                        ? 'border-transparent bg-[linear-gradient(135deg,color-mix(in_srgb,var(--aura-primary)_30%,transparent),color-mix(in_srgb,var(--aura-secondary)_16%,transparent))] text-[var(--aura-text)] shadow-[0_18px_48px_-28px_var(--aura-glow)]'
                        : 'border-transparent text-[var(--aura-text-muted)] hover:border-[var(--aura-border)] hover:bg-[var(--aura-surface)] hover:text-[var(--aura-text)]',
                    )}
                  >
                    <Icon
                      className={cn(
                        'h-5 w-5 shrink-0 transition-colors',
                        isActive
                          ? 'text-[var(--aura-primary)]'
                          : 'text-[var(--aura-text-muted)] group-hover:text-[var(--aura-primary)]',
                      )}
                    />
                    <span className="truncate font-medium">{item.label}</span>
                  </RouteTransitionLink>
                )
              })}
            </nav>

            <div className="mt-6 rounded-[2rem] border border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_72%,transparent)] p-5 lg:mt-auto">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] font-semibold text-[#1d1830] shadow-[0_16px_32px_-20px_var(--aura-glow)]">
                  {sharedUserAccount.initials}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-[var(--aura-text)]">
                    {sharedUserAccount.name}
                  </p>
                  <p className="truncate text-[11px] uppercase tracking-[0.24em] text-[var(--aura-text-soft)]">
                    {sharedUserAccount.status}
                  </p>
                </div>
              </div>
              <p className="mt-4 text-xs leading-6 text-[var(--aura-text-muted)]">
                {sharedUserAccount.description}
              </p>
            </div>
          </div>
        </aside>

        <div className="flex flex-1 flex-col lg:ml-80">
          <header
            className="sticky top-0 z-20 flex items-center justify-between border-b border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-bg)_82%,transparent)] px-4 py-4 backdrop-blur-xl sm:px-6 lg:px-10"
            style={{ viewTransitionName: 'aura-header' }}
          >
            <div className="min-w-0">{title}</div>
            <div className="flex items-center gap-2 sm:gap-3">
              {actions ??
                (showDefaultAction ? (
                  <button
                    type="button"
                    className="flex h-11 w-11 items-center justify-center rounded-full border border-[var(--aura-border)] text-[var(--aura-text-muted)] transition-colors hover:text-[var(--aura-primary)]"
                    aria-label="Open User Account"
                  >
                    <CircleUserRound className="h-5 w-5" />
                  </button>
                ) : null)}
            </div>
          </header>

          <ViewTransition
            enter={{
              'nav-forward': 'nav-forward',
              'nav-back': 'nav-back',
              default: 'page-fade',
            }}
            exit={{
              'nav-forward': 'nav-forward',
              'nav-back': 'nav-back',
              default: 'page-fade',
            }}
            default="page-fade"
          >
            <main
              className={cn(
                'aura-page flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-10',
                contentClassName,
              )}
            >
              {children}
            </main>
          </ViewTransition>
        </div>
      </div>
    </div>
  )
}
