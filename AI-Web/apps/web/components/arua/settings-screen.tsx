'use client'

import { useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { Globe, ShieldCheck, Sparkles } from 'lucide-react'
import { AruaAppShell } from '@/components/arua/app-shell'
import { AppearanceToggle } from '@/components/arua/appearance-toggle'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { useI18n } from '@/lib/i18n'
import { useUserStore } from '@/store/user'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

const sexOptions = [
  { label: 'Male', value: '1' },
  { label: 'Female', value: '2' },
] as const

export function AruaSettingsScreen() {
  const { locale, setLocale, t } = useI18n()
  const token = useUserStore((state) => state.token)
  const userInfo = useUserStore((state) => state.userInfo)
  const getUserInfo = useUserStore((state) => state.getUserInfo)
  const updateUserInfo = useUserStore((state) => state.updateUserInfo)
  const deleteCurrentUser = useUserStore((state) => state.deleteCurrentUser)
  const logoutRemote = useUserStore((state) => state.logoutRemote)
  const logout = useUserStore((state) => state.logout)
  const router = useRouter()
  const [form, setForm] = useState({
    username: '',
    email: '',
    age: '',
    sex: '',
  })
  const [isLoadingProfile, setIsLoadingProfile] = useState(false)
  const [isSavingProfile, setIsSavingProfile] = useState(false)
  const [isDeletingAccount, setIsDeletingAccount] = useState(false)

  useEffect(() => {
    if (!token) return

    setIsLoadingProfile(true)
    getUserInfo()
      .catch(() => {
        toast.error(t('chat.accountSyncFailed'), {
          description: t('chat.accountSyncFailedDescription'),
          position: 'top-center',
        })
      })
      .finally(() => setIsLoadingProfile(false))
  }, [getUserInfo, t, token])

  useEffect(() => {
    setForm({
      username: userInfo.username ?? '',
      email: userInfo.email ?? '',
      age: typeof userInfo.age === 'number' ? String(userInfo.age) : '',
      sex: typeof userInfo.sex === 'number' ? String(userInfo.sex) : '',
    })
  }, [userInfo])

  const usernameInitial = useMemo(
    () => form.username.trim().slice(0, 1).toUpperCase() || 'U',
    [form.username],
  )

  const handleFieldChange =
    (field: keyof typeof form) => (event: ChangeEvent<HTMLInputElement>) => {
      setForm((current) => ({
        ...current,
        [field]: event.target.value,
      }))
    }

  const handleSaveProfile = async () => {
    if (!form.username.trim()) {
      toast.error(t('settings.profileSaveFailed'), {
        description: t('settings.usernameRequired'),
        position: 'top-center',
      })
      return
    }

    setIsSavingProfile(true)

    try {
      await updateUserInfo({
        username: form.username.trim(),
        email: form.email.trim() || undefined,
        age: form.age ? Number(form.age) : undefined,
        sex: form.sex ? Number(form.sex) : undefined,
      })
      toast.success(t('settings.profileSaved'), {
        position: 'top-center',
      })
    } catch {
      toast.error(t('settings.profileSaveFailed'), {
        description: t('chat.tryAgain'),
        position: 'top-center',
      })
    } finally {
      setIsSavingProfile(false)
    }
  }

  const handleSignOut = async () => {
    try {
      await logoutRemote()
    } catch {
      logout()
    } finally {
      router.replace('/login')
    }
  }

  const handleDeleteAccount = async () => {
    if (!userInfo.username || isDeletingAccount) {
      return
    }

    setIsDeletingAccount(true)

    try {
      await deleteCurrentUser()
      toast.success(t('settings.accountDeleted'), {
        position: 'top-center',
      })
      router.replace('/login')
    } catch {
      toast.error(t('settings.accountDeleteFailed'), {
        description: t('chat.tryAgain'),
        position: 'top-center',
      })
    } finally {
      setIsDeletingAccount(false)
    }
  }

  return (
    <AruaAppShell
      active="settings"
      title={
        <h2 className="text-2xl font-semibold tracking-tight text-[var(--aura-primary)]">
          {t('settings.title')}
        </h2>
      }
    >
      <div className="mx-auto w-full max-w-7xl gap-8 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <div className="flex flex-col gap-8">
          <section>
            <div className="flex items-center gap-4 mb-6">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-base font-semibold text-[#251739]">
                {usernameInitial}
              </div>
              <h3 className="text-3xl font-semibold tracking-tight text-[var(--aura-text)]">
                {t('settings.userProfile')}
              </h3>
            </div>
            <Card className="rounded-[1.75rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_86%,transparent)] py-0 shadow-[0_20px_60px_-42px_var(--aura-glow)]">
              <CardContent className="p-6 sm:p-8">
                <div className="grid gap-6">
                  <div className="space-y-2">
                    <Label className="text-[11px] tracking-[0.24em] text-[var(--aura-text-muted)] uppercase">
                      {t('settings.displayName')}
                    </Label>
                    <Input
                      value={form.username}
                      onChange={handleFieldChange('username')}
                      placeholder={t('settings.displayNamePlaceholder')}
                      className="h-11 rounded-2xl border-[var(--aura-border)] bg-[var(--aura-surface-strong)] px-4 text-sm text-[var(--aura-text)]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[11px] tracking-[0.24em] text-[var(--aura-text-muted)] uppercase">
                      {t('settings.email')}
                    </Label>
                    <Input
                      value={form.email}
                      onChange={handleFieldChange('email')}
                      placeholder={t('settings.emailPlaceholder')}
                      className="h-11 rounded-2xl border-[var(--aura-border)] bg-[var(--aura-surface-strong)] px-4 text-sm text-[var(--aura-text)]"
                    />
                  </div>
                  <div className="grid gap-6 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label className="text-[11px] tracking-[0.24em] text-[var(--aura-text-muted)] uppercase">
                        {t('settings.age')}
                      </Label>
                      <Input
                        value={form.age}
                        onChange={handleFieldChange('age')}
                        type="number"
                        min={1}
                        max={120}
                        placeholder={t('settings.agePlaceholder')}
                        className="h-11 rounded-2xl border-[var(--aura-border)] bg-[var(--aura-surface-strong)] px-4 text-sm text-[var(--aura-text)]"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[11px] tracking-[0.24em] text-[var(--aura-text-muted)] uppercase">
                        {t('settings.sex')}
                      </Label>
                      <RadioGroup
                        value={form.sex}
                        onValueChange={(value) =>
                          setForm((current) => ({
                            ...current,
                            sex: value,
                          }))
                        }
                        className="grid grid-cols-2 gap-2"
                      >
                        {sexOptions.map((option) => {
                          const isActive = form.sex === option.value

                          return (
                            <label
                              key={option.value}
                              htmlFor={`settings-sex-${option.value}`}
                              className={cn(
                                'flex h-11 cursor-pointer items-center justify-between gap-3 rounded-2xl border border-[var(--aura-border)] bg-[var(--aura-surface-strong)] px-4 text-sm text-[var(--aura-text-muted)] transition-all duration-200 hover:border-[var(--aura-border-strong)] hover:bg-[var(--aura-surface)] hover:text-[var(--aura-text)]',
                                isActive &&
                                  'border-[var(--aura-border-strong)] bg-[var(--aura-primary-soft)] text-[var(--aura-primary)]',
                              )}
                            >
                              <span>
                                {t(option.label === 'Male' ? 'auth.male' : 'auth.female')}
                              </span>
                              <RadioGroupItem
                                id={`settings-sex-${option.value}`}
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
                    </div>
                  </div>
                </div>
                <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <Button
                    type="button"
                    size="lg"
                    disabled={isLoadingProfile || isSavingProfile}
                    onClick={handleSaveProfile}
                    className="rounded-2xl bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] px-6 text-sm font-semibold text-[#251739] shadow-[0_20px_40px_-24px_var(--aura-glow)] disabled:opacity-60"
                  >
                    {isSavingProfile ? t('settings.savingProfile') : t('settings.saveProfile')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="space-y-4">
              <div className="flex items-center gap-3">
                <Globe className="h-5 w-5 text-[var(--aura-secondary)]" />
                <h4 className="text-2xl font-semibold text-[var(--aura-text)]">
                  {t('settings.language')}
                </h4>
              </div>
              <Card className="rounded-[1.5rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_86%,transparent)] py-0">
                <CardContent className="space-y-4 p-5">
                  <div className="grid grid-cols-2 gap-3">
                    <Button
                      type="button"
                      variant={locale === 'zh-CN' ? 'default' : 'outline'}
                      className="rounded-2xl"
                      onClick={() => setLocale('zh-CN')}
                    >
                      中文
                    </Button>
                    <Button
                      type="button"
                      variant={locale === 'en-US' ? 'default' : 'outline'}
                      className="rounded-2xl"
                      onClick={() => setLocale('en-US')}
                    >
                      English
                    </Button>
                  </div>
                  <p className="text-sm leading-7 text-[var(--aura-text-muted)]">
                    {t('settings.languageHint')}
                  </p>
                </CardContent>
              </Card>
            </section>

            <section className="space-y-4">
              <div className="flex items-center gap-3">
                <Sparkles className="h-5 w-5 text-[var(--aura-secondary)]" />
                <h4 className="text-2xl font-semibold text-[var(--aura-text)]">
                  {t('settings.appearance')}
                </h4>
              </div>
              <Card className="rounded-[1.5rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_86%,transparent)] py-0">
                <CardContent className="p-5">
                  <AppearanceToggle />
                </CardContent>
              </Card>
            </section>
          </div>

          <section className="space-y-5 pt-1">
            <div className="flex items-center gap-4">
              <ShieldCheck className="h-6 w-6 text-[#ffb8b0]" />
              <h3 className="text-3xl font-semibold tracking-tight text-[var(--aura-text)]">
                {t('settings.security')}
              </h3>
            </div>

            <Card className="rounded-[1.75rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_86%,transparent)] py-0">
              <CardContent className="space-y-6 p-6 sm:p-8">
                <div className="flex flex-col gap-6 border-b border-[var(--aura-border)] pb-6 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h4 className="text-2xl font-semibold text-[var(--aura-text)]">
                      {t('settings.sessions')}
                    </h4>
                    <p className="mt-2 text-sm leading-7 text-[var(--aura-text-muted)]">
                      {t('settings.sessionsHint')}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="lg"
                    onClick={handleSignOut}
                    className="rounded-2xl border-[var(--aura-border-strong)] bg-transparent px-6 text-sm font-semibold text-[var(--aura-text)] disabled:opacity-60"
                  >
                    {t('settings.signOut')}
                  </Button>
                </div>

                <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h4 className="text-2xl font-semibold text-[#ffb8b0]">
                      {t('settings.dangerZone')}
                    </h4>
                    <p className="mt-2 text-sm leading-7 text-[var(--aura-text-muted)]">
                      {t('settings.dangerHint')}
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="lg"
                    disabled={!userInfo.username || isDeletingAccount}
                    onClick={handleDeleteAccount}
                    className="rounded-2xl bg-[#ffb8b0] px-6 text-sm font-bold text-[#34151a] shadow-[0_20px_40px_-26px_rgba(255,184,176,0.65)] disabled:opacity-60"
                  >
                    {isDeletingAccount ? t('settings.deletingAccount') : t('settings.deleteAccount')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </section>
        </div>
      </div>
    </AruaAppShell>
  )
}
