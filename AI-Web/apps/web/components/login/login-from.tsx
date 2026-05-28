'use client'

import type { ChangeEvent, ComponentProps, FormEvent } from 'react'
import { useState } from 'react'
import { LoaderCircle, LockKeyhole, Mail, User } from 'lucide-react'
import type { LoginForm as LoginFormValues } from '@ai-web/types'
import { user } from '@/apis/user'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

type AuthMode = 'login' | 'register'

export function LoginForm({ className, ...props }: ComponentProps<'div'>) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [submitting, setSubmitting] = useState(false)
  const [formData, setFormData] = useState<Partial<LoginFormValues>>({
    username: '',
    password: '',
    email: '',
  })

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target

    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)

    try {
      const response = await user.login<unknown>('/user/Login', formData)

      toast.success('Success', {
        description: response.message,
        position: 'top-center',
      })
    } catch {
      toast.error('Login failed', {
        description: 'Please verify your account information and try again.',
        position: 'top-center',
      })
    } finally {
      setSubmitting(false)
    }
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
            <Field orientation="horizontal">
              <User />
              <Input
                type="text"
                name="username"
                placeholder={mode === 'login' ? 'Enter your username' : 'Choose a username'}
                value={formData.username ?? ''}
                onChange={handleChange}
              />
            </Field>

            {mode === 'register' ? (
              <Field orientation="horizontal">
                <Mail />
                <Input
                  type="email"
                  name="email"
                  placeholder="you@example.com"
                  value={formData.email ?? ''}
                  onChange={handleChange}
                />
              </Field>
            ) : null}

            <Field orientation="horizontal">
              <LockKeyhole />
              <Input
                type="password"
                name="password"
                placeholder={mode === 'login' ? 'Enter your password' : 'Create a password'}
                value={formData.password ?? ''}
                onChange={handleChange}
              />
            </Field>

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
