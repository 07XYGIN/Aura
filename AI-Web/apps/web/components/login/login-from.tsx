'use client'

import type { ChangeEvent, ComponentProps, FormEvent } from 'react'
import { useEffect, useState } from 'react'
import { Cake, KeyRound, LoaderCircle, LockKeyhole, Mail, User } from 'lucide-react'
import { user } from '@/apis/user'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { cn } from '@/lib/utils'
import type { AuthFormValues, AuthMode, SexOption, UserSex } from '@/types/auth'
import { toast } from 'sonner'
import { useUserStore } from '@/store/user'
import { useRouter, useSearchParams } from "next/navigation";
import { useI18n } from '@/lib/i18n'
import { setAuthTokenCookie } from '@/lib/auth-token'
const sexOptions: SexOption[] = [
  { label: 'Male', value: '1' },
  { label: 'Female', value: '0' },
]

const toUserSex = (value?: string): UserSex | undefined => {
  if (value === '1') {
    return 1
  }
  if (value === '0') {
    return 0
  }

  return undefined
}

export function LoginForm({ className, ...props }: ComponentProps<'div'>) {
  const { t } = useI18n()
  const [mode, setMode] = useState<AuthMode>('login')
  const [submitting, setSubmitting] = useState(false)
  const [formData, setFormData] = useState<AuthFormValues>({
    username: '',
    password: '',
    email: '',
    age: '',
    sex: '',
    inviteCode: '',
  })
  const setToken = useUserStore((state) => state.setToken);
  const router = useRouter();
  const searchParams = useSearchParams();
  const authReason = searchParams.get('reason');

  useEffect(() => {
    if (authReason === 'missing') {
      toast.error('请先登录', {
        position: 'top-center',
      })
    }

    if (authReason === 'expired') {
      toast.error('登录已过期，请重新登录', {
        position: 'top-center',
      })
    }

    if (authReason === 'invalid') {
      toast.error('登录状态非法，请重新登录', {
        position: 'top-center',
      })
    }
  }, [authReason])
  const handleForgotPassword = () => {
    toast.info(t('auth.forgotPasswordPending'), {
      description: t('auth.forgotPasswordDescription'),
      position: 'top-center',
    })
  }

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target

    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const handleSexChange = (value: AuthFormValues['sex']) => {
    setFormData((prev) => ({
      ...prev,
      sex: value,
    }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)

    const payload =
        mode === 'register'
            ? {
                  username: formData.username ?? '',
                  password: formData.password ?? '',
                  email: formData.email ?? '',
                  sex: toUserSex(formData.sex),
                  age: formData.age ? Number(formData.age) : undefined,
                  inviteCode: formData.inviteCode ?? '',
              }
            : {
                  username: formData.username ?? '',
                  password: formData.password ?? '',
              }

    if (mode === 'register') {
        try {
            const {message} = await user.register<unknown>('/api/user/register', payload)
            toast.success(t('auth.accountCreated'), {
                description: message,
                position: 'top-center',
            })

        } catch (error) {
            toast.error(t('auth.registrationFailed'), {
                description: error instanceof Error ? error.message : t('auth.verifyRegister'),
                position: 'top-center',
            })
        } finally {
          setSubmitting(false)
        }
    } else {
        try {
            const response = await user.login<unknown>('/api/user/login', payload)
            if (!response.token) {
                toast.error(t('auth.loginFailed'), {
                    description: response.message || t('auth.verifyLogin'),
                    position: 'top-center',
                })
                return
            }

            toast.success(t('auth.success'), {
                description: response.message,
                position: 'top-center',
            })
            setAuthTokenCookie(response.token)
            setToken(response.token)
            router.replace(searchParams.get('redirect') || '/')
        } catch (error) {
            toast.error(mode === 'login' ? t('auth.loginFailed') : t('auth.registrationFailed'), {
                description:
                    error instanceof Error
                        ? error.message
                        : mode === 'login'
                        ? t('auth.verifyLogin')
                        : t('auth.verifyRegister'),
                position: 'top-center',
            })
        } finally {
            setSubmitting(false)
        }
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
                'border-b-2 px-2 pb-3 text-sm font-semibold tracking-[0.18em] uppercase transition-colors',
                mode === 'login'
                  ? 'border-[var(--aura-primary)] text-[var(--aura-primary)]'
                  : 'border-transparent text-[var(--aura-text-muted)] hover:text-[var(--aura-text)]',
              )}
            >
              {t('auth.login')}
            </button>
            <button
              type="button"
              onClick={() => setMode('register')}
              className={cn(
                'border-b-2 px-2 pb-3 text-sm font-semibold tracking-[0.18em] uppercase transition-colors',
                mode === 'register'
                  ? 'border-[var(--aura-primary)] text-[var(--aura-primary)]'
                  : 'border-transparent text-[var(--aura-text-muted)] hover:text-[var(--aura-text)]',
              )}
            >
              {t('auth.register')}
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <Field orientation="horizontal">
              <User />
              <Input
                type="text"
                name="username"
                placeholder={mode === 'login' ? t('auth.usernameLogin') : t('auth.usernameRegister')}
                value={formData.username ?? ''}
                onChange={handleChange}
              />
            </Field>

            {mode === 'register' ? (
              <div className="space-y-5">
                <Field orientation="horizontal">
                  <Mail />
                  <Input
                    type="email"
                    name="email"
                    placeholder={t('auth.email')}
                    value={formData.email ?? ''}
                    onChange={handleChange}
                  />
                </Field>

                <Field orientation="horizontal">
                  <Cake />
                  <Input
                    type="number"
                    min="0"
                    name="age"
                    placeholder={t('auth.age')}
                    value={formData.age ?? ''}
                    onChange={handleChange}
                  />
                </Field>

                <Field orientation="horizontal">
                  <KeyRound />
                  <Input
                    type="text"
                    name="inviteCode"
                    placeholder={t('auth.inviteCode')}
                    value={formData.inviteCode ?? ''}
                    onChange={handleChange}
                  />
                </Field>
              </div>
            ) : null}

            <Field orientation="horizontal">
              <LockKeyhole />
              <Input
                type="password"
                name="password"
                placeholder={mode === 'login' ? t('auth.passwordLogin') : t('auth.passwordRegister')}
                value={formData.password ?? ''}
                onChange={handleChange}
              />
            </Field>

            {mode === 'register' ? (
              <RadioGroup
                value={formData.sex ?? ''}
                onValueChange={(value) => handleSexChange(value as AuthFormValues['sex'])}
                className="grid grid-cols-2 gap-2"
              >
                {sexOptions.map((option) => {
                  const isActive = formData.sex === option.value

                  return (
                    <label
                      key={option.value}
                      htmlFor={`sex-${option.value}`}
                      className={cn(
                        'flex cursor-pointer items-center justify-between gap-3 rounded-2xl border border-[var(--aura-border)] bg-[var(--aura-surface-muted)] px-4 py-3 text-sm text-[var(--aura-text-muted)] transition-all duration-200 hover:border-[var(--aura-border-strong)] hover:bg-[var(--aura-surface)] hover:text-[var(--aura-text)]',
                        isActive &&
                          'border-[var(--aura-border-strong)] bg-[var(--aura-primary-soft)] text-[var(--aura-primary)]',
                      )}
                    >
                      <span>{t(option.label === 'Male' ? 'auth.male' : 'auth.female')}</span>
                      <RadioGroupItem
                        id={`sex-${option.value}`}
                        value={option.value}
                        className={cn(
                          'border-[var(--aura-border-strong)] text-[var(--aura-primary)]',
                          isActive && 'border-[var(--aura-primary)]',
                        )}
                      />
                    </label>
                  )
                })}
              </RadioGroup>
            ) : null}

            {mode === 'login' ? (
              <div className="flex flex-col gap-3 pt-1 text-sm text-[var(--aura-text-muted)] sm:flex-row sm:items-center sm:justify-between">
                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-[var(--aura-border)] bg-[var(--aura-surface-strong)] text-[var(--aura-primary)]"
                  />
                  <span>{t('auth.rememberMe')}</span>
                </label>
                <button
                  type="button"
                  onClick={handleForgotPassword}
                  className="text-left text-[var(--aura-primary)] transition-colors hover:text-[var(--aura-secondary)]"
                >
                  {t('auth.forgotPassword')}
                </button>
              </div>
            ) : null}

            <Button
              type="submit"
              size="lg"
              disabled={submitting}
              className={cn(
                'flex w-full items-center justify-center gap-3 rounded-2xl px-5 text-sm font-semibold tracking-[0.28em] uppercase transition-all duration-300',
                mode === 'login'
                  ? 'bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-[#241637] shadow-[0_26px_44px_-28px_var(--aura-glow)] hover:scale-[1.01]'
                  : 'bg-[var(--aura-primary-soft)] text-[var(--aura-text)] hover:border-[var(--aura-border-strong)]',
                submitting && 'cursor-not-allowed opacity-80',
              )}
            >
              {submitting ? <LoaderCircle className="h-5 w-5 animate-spin" /> : null}
              {mode === 'login' ? t('auth.signIn') : t('auth.createAccount')}
            </Button>
          </form>
        </CardContent>
      </Card>

      <p className="px-6 text-center text-base leading-8 text-[var(--aura-text-muted)]">
        {t('auth.protected')}
        <br />
        {t('auth.termsPrefix')}{' '}
        <span className="text-[var(--aura-primary)]">{t('auth.terms')}</span>.
      </p>
    </div>
  )
}
