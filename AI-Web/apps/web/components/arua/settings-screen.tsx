'use client'

import { Globe, ShieldCheck, Sparkles, UserRound } from 'lucide-react'
import { AruaAppShell } from '@/components/arua/app-shell'
import { AppearanceToggle } from '@/components/arua/appearance-toggle'
import { sharedUserAccount } from '@/components/arua/data'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useI18n } from '@/lib/i18n'
import { useUserStore } from '@/store/user'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

export function AruaSettingsScreen() {
  const { locale, setLocale, t } = useI18n()
  const logout = useUserStore((state) => state.logout)
  const router = useRouter()

  const handleSignOut = () => {
    logout()
    router.replace('/login')
  }

  const handleNotReady = () => {
    toast.info(t('settings.notReady'), {
      description: t('settings.notReadyDescription'),
      position: 'top-center',
    })
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
      <div className="mx-auto grid w-full max-w-7xl gap-8 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <aside className="space-y-6 xl:sticky xl:top-28 xl:self-start">
          <Card className="rounded-[2rem] border-[var(--aura-border)] bg-[linear-gradient(180deg,color-mix(in_srgb,var(--aura-surface-solid)_82%,transparent),color-mix(in_srgb,var(--aura-primary)_10%,transparent))] py-0 shadow-[0_28px_72px_-56px_var(--aura-glow)]">
            <CardContent className="p-6">
              <div className="flex h-14 w-14 items-center justify-center rounded-[1.25rem] bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] text-xl font-semibold text-[#211634]">
                {sharedUserAccount.initials}
              </div>
              <p className="mt-5 text-[11px] tracking-[0.32em] text-[var(--aura-text-soft)] uppercase">
                {t('settings.accountOverview')}
              </p>
              <CardTitle className="mt-3 text-2xl font-semibold text-[var(--aura-text)]">
                {t(sharedUserAccount.name as Parameters<typeof t>[0])}
              </CardTitle>
              <p className="mt-2 text-sm font-medium text-[var(--aura-primary)]">
                {t(sharedUserAccount.status as Parameters<typeof t>[0])}
              </p>
              <p className="mt-3 text-sm leading-7 text-[var(--aura-text-muted)]">
                {t(sharedUserAccount.description as Parameters<typeof t>[0])}
              </p>
            </CardContent>
          </Card>
        </aside>

        <div className="flex flex-col gap-8">
          <section className="space-y-5">
            <div className="flex items-center gap-4">
              <UserRound className="h-6 w-6 text-[var(--aura-primary)]" />
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
                      placeholder={t('settings.displayNamePlaceholder')}
                      className="h-11 rounded-2xl border-[var(--aura-border)] bg-[var(--aura-surface-strong)] px-4 text-sm text-[var(--aura-text)]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[11px] tracking-[0.24em] text-[var(--aura-text-muted)] uppercase">
                      {t('settings.email')}
                    </Label>
                    <Input
                      placeholder={t('settings.emailPlaceholder')}
                      className="h-11 rounded-2xl border-[var(--aura-border)] bg-[var(--aura-surface-strong)] px-4 text-sm text-[var(--aura-text)]"
                    />
                  </div>
                </div>
                <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm leading-6 text-[var(--aura-text-muted)]">
                    {t('settings.profileHint')}
                  </p>
                  <Button
                    type="button"
                    size="lg"
                    onClick={handleNotReady}
                    className="rounded-2xl bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] px-6 text-sm font-semibold text-[#251739] opacity-60 shadow-[0_20px_40px_-24px_var(--aura-glow)]"
                  >
                    {t('settings.saveProfile')}
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
                    onClick={handleNotReady}
                    className="rounded-2xl bg-[#ffb8b0] px-6 text-sm font-bold text-[#34151a] opacity-60 shadow-[0_20px_40px_-26px_rgba(255,184,176,0.65)]"
                  >
                    {t('settings.deleteAccount')}
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
