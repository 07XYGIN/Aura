import { Globe, ShieldCheck, Sparkles, UserRound } from 'lucide-react'
import { AruaAppShell } from '@/components/arua/app-shell'
import { AppearanceToggle } from '@/components/arua/appearance-toggle'
import { sharedUserAccount } from '@/components/arua/data'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function AruaSettingsScreen() {
  return (
    <AruaAppShell
      active="settings"
      title={
        <h2 className="text-2xl font-semibold tracking-tight text-[var(--aura-primary)]">
          Settings
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
                Account overview
              </p>
              <CardTitle className="mt-3 text-2xl font-semibold text-[var(--aura-text)]">
                {sharedUserAccount.name}
              </CardTitle>
              <p className="mt-2 text-sm font-medium text-[var(--aura-primary)]">
                {sharedUserAccount.status}
              </p>
              <p className="mt-3 text-sm leading-7 text-[var(--aura-text-muted)]">
                {sharedUserAccount.description}
              </p>
            </CardContent>
          </Card>
        </aside>

        <div className="flex flex-col gap-8">
          <section className="space-y-5">
            <div className="flex items-center gap-4">
              <UserRound className="h-6 w-6 text-[var(--aura-primary)]" />
              <h3 className="text-3xl font-semibold tracking-tight text-[var(--aura-text)]">
                User profile
              </h3>
            </div>
            <Card className="rounded-[1.75rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_86%,transparent)] py-0 shadow-[0_20px_60px_-42px_var(--aura-glow)]">
              <CardContent className="p-6 sm:p-8">
                <div className="grid gap-6">
                  <div className="space-y-2">
                    <Label className="text-[11px] tracking-[0.24em] text-[var(--aura-text-muted)] uppercase">
                      Display name
                    </Label>
                    <Input
                      placeholder="Will load from backend profile"
                      className="h-11 rounded-2xl border-[var(--aura-border)] bg-[var(--aura-surface-strong)] px-4 text-sm text-[var(--aura-text)]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[11px] tracking-[0.24em] text-[var(--aura-text-muted)] uppercase">
                      Email address
                    </Label>
                    <Input
                      placeholder="Will load from backend account"
                      className="h-11 rounded-2xl border-[var(--aura-border)] bg-[var(--aura-surface-strong)] px-4 text-sm text-[var(--aura-text)]"
                    />
                  </div>
                </div>
                <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm leading-6 text-[var(--aura-text-muted)]">
                    Form fields are ready, but persistence stays disabled until the profile API is
                    connected.
                  </p>
                  <Button
                    type="button"
                    size="lg"
                    disabled
                    className="rounded-2xl bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] px-6 text-sm font-semibold text-[#251739] opacity-60 shadow-[0_20px_40px_-24px_var(--aura-glow)]"
                  >
                    Save profile
                  </Button>
                </div>
              </CardContent>
            </Card>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="space-y-4">
              <div className="flex items-center gap-3">
                <Globe className="h-5 w-5 text-[var(--aura-secondary)]" />
                <h4 className="text-2xl font-semibold text-[var(--aura-text)]">Language</h4>
              </div>
              <Card className="rounded-[1.5rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_86%,transparent)] py-0">
                <CardContent className="space-y-4 p-5">
                  <Input
                    placeholder="Language preference will sync from backend"
                    className="h-11 rounded-2xl border-[var(--aura-border)] bg-[var(--aura-surface-strong)] px-4 text-sm text-[var(--aura-text)]"
                  />
                  <p className="text-sm leading-7 text-[var(--aura-text-muted)]">
                    Once connected, Arua will mirror the user account language and locale directly
                    from persisted settings.
                  </p>
                </CardContent>
              </Card>
            </section>

            <section className="space-y-4">
              <div className="flex items-center gap-3">
                <Sparkles className="h-5 w-5 text-[var(--aura-secondary)]" />
                <h4 className="text-2xl font-semibold text-[var(--aura-text)]">Appearance</h4>
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
                Security & account
              </h3>
            </div>

            <Card className="rounded-[1.75rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_86%,transparent)] py-0">
              <CardContent className="space-y-6 p-6 sm:p-8">
                <div className="flex flex-col gap-6 border-b border-[var(--aura-border)] pb-6 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h4 className="text-2xl font-semibold text-[var(--aura-text)]">
                      Session controls
                    </h4>
                    <p className="mt-2 text-sm leading-7 text-[var(--aura-text-muted)]">
                      Sign-out and multi-device session management will activate with the auth
                      backend.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="lg"
                    disabled
                    className="rounded-2xl border-[var(--aura-border-strong)] bg-transparent px-6 text-sm font-semibold text-[var(--aura-text)] disabled:opacity-60"
                  >
                    Sign out
                  </Button>
                </div>

                <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h4 className="text-2xl font-semibold text-[#ffb8b0]">Danger zone</h4>
                    <p className="mt-2 text-sm leading-7 text-[var(--aura-text-muted)]">
                      Destructive account actions remain disabled until permission and audit flows
                      are available from the backend.
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="lg"
                    disabled
                    className="rounded-2xl bg-[#ffb8b0] px-6 text-sm font-bold text-[#34151a] opacity-60 shadow-[0_20px_40px_-26px_rgba(255,184,176,0.65)]"
                  >
                    Delete account
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
