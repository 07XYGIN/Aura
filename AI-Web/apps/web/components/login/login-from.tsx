'use client'

import type { ComponentProps, ComponentType, FormEvent, ReactNode } from 'react'
import { useState } from 'react'
import { LoaderCircle, LockKeyhole, Mail, UserRound } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type AuthMode = 'login' | 'register'

function AuthField({
  label,
  icon: Icon,
  children,
}: {
  label: string
  icon: ComponentType<{ className?: string }>
  children: ReactNode
}) {
  return (
    <label className="space-y-2">
      <Label className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--aura-text-muted)]">
        {label}
      </Label>
      <div className="group flex items-center gap-3 rounded-2xl border border-[var(--aura-border)] bg-[var(--aura-surface-muted)] px-4 py-3 transition-all duration-300 focus-within:border-[var(--aura-border-strong)] focus-within:shadow-[0_0_0_1px_var(--aura-border-strong)]">
        <Icon className="h-5 w-5 shrink-0 text-[var(--aura-text-soft)] transition-colors group-focus-within:text-[var(--aura-primary)]" />
        {children}
      </div>
    </label>
  )
}

export function LoginForm({ className, ...props }: ComponentProps<'div'>) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)

    window.setTimeout(() => {
      setSubmitting(false)
    }, 1200)
  }

  return (
    <div className={cn('flex flex-col gap-10', className)} {...props}>
      <Card className="aura-glass rounded-[1.75rem] border-[var(--aura-border)] bg-transparent py-0">
        <CardContent className="px-6 py-7 sm:px-10 sm:py-9">
          <div className="mb-8 flex items-center justify-center gap-10 border-b border-[var(--aura-border)] pb-4">
            <button
              type="button"
              onClick={() => setMode('login')}
              className={cn(
                'border-b-2 px-2 pb-3 text-sm font-semibold uppercase tracking-[0.18em] transition-colors',
                mode === 'login'
                  ? 'border-[var(--aura-primary)] text-[var(--aura-primary)]'
                  : 'border-transparent text-[var(--aura-text-muted)] hover:text-[var(--aura-text)]',
              )}
            >
              Login
            </button>
            <button
              type="button"
              onClick={() => setMode('register')}
              className={cn(
                'border-b-2 px-2 pb-3 text-sm font-semibold uppercase tracking-[0.18em] transition-colors',
                mode === 'register'
                  ? 'border-[var(--aura-primary)] text-[var(--aura-primary)]'
                  : 'border-transparent text-[var(--aura-text-muted)] hover:text-[var(--aura-text)]',
              )}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <AuthField label="Username" icon={UserRound}>
              <Input
                type="text"
                placeholder={mode === 'login' ? 'Enter your username' : 'Choose a username'}
                className="h-auto border-0 bg-transparent px-0 py-0 text-sm text-[var(--aura-text)] shadow-none placeholder:text-[var(--aura-text-soft)] focus-visible:ring-0"
              />
            </AuthField>

            {mode === 'register' ? (
              <AuthField label="Email Address" icon={Mail}>
                <Input
                  type="email"
                  placeholder="you@example.com"
                  className="h-auto border-0 bg-transparent px-0 py-0 text-sm text-[var(--aura-text)] shadow-none placeholder:text-[var(--aura-text-soft)] focus-visible:ring-0"
                />
              </AuthField>
            ) : null}

            <AuthField label="Password" icon={LockKeyhole}>
              <Input
                type="password"
                placeholder={mode === 'login' ? 'Enter your password' : 'Create a password'}
                className="h-auto border-0 bg-transparent px-0 py-0 text-sm text-[var(--aura-text)] shadow-none placeholder:text-[var(--aura-text-soft)] focus-visible:ring-0"
              />
            </AuthField>

            {mode === 'login' ? (
              <div className="flex flex-col gap-3 pt-1 text-sm text-[var(--aura-text-muted)] sm:flex-row sm:items-center sm:justify-between">
                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-[var(--aura-border)] bg-[var(--aura-surface-strong)] text-[var(--aura-primary)]"
                  />
                  <span>Remember me</span>
                </label>
                <button
                  type="button"
                  className="text-left text-[var(--aura-primary)] transition-colors hover:text-[var(--aura-secondary)]"
                >
                  Forgot password?
                </button>
              </div>
            ) : null}

            <Button
              type="submit"
              size="lg"
              disabled={submitting}
              className={cn(
                'flex w-full items-center justify-center gap-3 rounded-2xl px-5 text-sm font-semibold uppercase tracking-[0.28em] transition-all duration-300',
                mode === 'login'
                  ? 'bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-[#241637] shadow-[0_26px_44px_-28px_var(--aura-glow)] hover:scale-[1.01]'
                  : 'bg-[var(--aura-primary-soft)] text-[var(--aura-text)] hover:border-[var(--aura-border-strong)]',
                submitting && 'cursor-not-allowed opacity-80',
              )}
            >
              {submitting ? <LoaderCircle className="h-5 w-5 animate-spin" /> : null}
              {mode === 'login' ? 'Sign In' : 'Create Account'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <p className="px-6 text-center text-base leading-8 text-[var(--aura-text-muted)]">
        Protected by secure encryption.
        <br />
        By continuing, you agree to our{' '}
        <span className="text-[var(--aura-primary)]">Terms of Service</span>.
      </p>
    </div>
  )
}
