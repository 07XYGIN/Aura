import { Sparkles } from 'lucide-react'
import { AruaAppShell } from '@/components/arua/app-shell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardTitle } from '@/components/ui/card'

export function AruaMemoriesScreen() {
  return (
    <AruaAppShell
      active="memories"
      title={
        <h2 className="text-2xl font-semibold tracking-tight text-[var(--aura-primary)]">
          Memories
        </h2>
      }
    >
      <div className="mx-auto w-full max-w-7xl space-y-8">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_22rem]">
          <div className="space-y-4">
            <p className="text-xs font-semibold tracking-[0.38em] text-[var(--aura-primary)] uppercase">
              Memory workspace
            </p>
            <h3 className="text-3xl font-semibold tracking-tight text-[var(--aura-text)] sm:text-4xl">
              Backend-ready memory canvas
            </h3>
            <p className="max-w-3xl text-sm leading-8 text-[var(--aura-text-muted)]">
              This page is prepared for long-term memory records, indexing metadata, and recall
              diagnostics, but no personal memory data is rendered until the backend is integrated.
            </p>
          </div>

          <Card className="rounded-[2rem] border-[var(--aura-border)] bg-[linear-gradient(180deg,color-mix(in_srgb,var(--aura-surface-solid)_82%,transparent),color-mix(in_srgb,var(--aura-primary)_10%,transparent))] py-0 shadow-[0_30px_70px_-52px_var(--aura-glow)]">
            <CardContent className="p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-[1.1rem] bg-[var(--aura-primary-soft)]">
                <Sparkles className="h-5 w-5 text-[var(--aura-primary)]" />
              </div>
              <CardTitle className="mt-4 text-xl font-semibold text-[var(--aura-text)]">
                Memory sync pending
              </CardTitle>
              <CardDescription className="mt-3 text-sm leading-7 text-[var(--aura-text-muted)]">
                When the backend is live, summaries, tags, and recall confidence will stream into
                this layout without needing another UI refactor.
              </CardDescription>
            </CardContent>
          </Card>
        </div>

        <Card className="rounded-[2rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_86%,transparent)] py-0 shadow-[0_28px_72px_-54px_var(--aura-glow)]">
          <CardContent className="p-6 sm:p-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-2xl">
                <p className="text-[11px] tracking-[0.3em] text-[var(--aura-text-soft)] uppercase">
                  Empty state
                </p>
                <h4 className="mt-3 text-2xl font-semibold text-[var(--aura-text)]">
                  No memory entries are displayed yet
                </h4>
                <p className="mt-3 text-sm leading-7 text-[var(--aura-text-muted)]">
                  Future backend data can populate cards, grouped timelines, and retrieval filters
                  directly inside this section.
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="lg"
                disabled
                className="rounded-full border-[var(--aura-border)] bg-transparent px-5 text-xs tracking-[0.24em] text-[var(--aura-text)] uppercase disabled:opacity-60"
              >
                Awaiting memory service
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </AruaAppShell>
  )
}
