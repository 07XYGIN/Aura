'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Heart, Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { aura, type AuraRelationshipChapter } from '@/apis/aura'
import { AruaAppShell } from '@/components/arua/app-shell'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/lib/i18n'
import { useUserStore } from '@/store/user'

const formatChapterDate = (value: string | undefined, locale: string) => {
  if (!value) return null

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null

  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date)
}

export function AruaRelationshipScreen() {
  const { locale, t } = useI18n()
  const token = useUserStore((state) => state.token)
  const [chapters, setChapters] = useState<AuraRelationshipChapter[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const loadChapters = useCallback(async () => {
    if (!token) {
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    try {
      const response = await aura.getRelationshipChapters()
      setChapters(response.data?.items ?? [])
    } catch {
      toast.error(t('relationship.loadFailed'), {
        description: t('chat.tryAgain'),
        position: 'top-center',
      })
    } finally {
      setIsLoading(false)
    }
  }, [t, token])

  useEffect(() => {
    if (!token) {
      return
    }

    let cancelled = false
    aura
      .getRelationshipChapters()
      .then((response) => {
        if (!cancelled) {
          setChapters(response.data?.items ?? [])
        }
      })
      .catch(() => {
        if (!cancelled) {
          toast.error(t('relationship.loadFailed'), {
            description: t('chat.tryAgain'),
            position: 'top-center',
          })
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [t, token])

  const currentChapter = useMemo(
    () => chapters.find((chapter) => chapter.status === 'current') ?? null,
    [chapters],
  )
  const pastChapters = useMemo(
    () => chapters.filter((chapter) => chapter.status !== 'current'),
    [chapters],
  )

  return (
    <AruaAppShell
      active="relationship"
      title={
        <h2 className="text-2xl font-semibold text-[var(--aura-primary)]">
          {t('relationship.title')}
        </h2>
      }
      actions={
        <Button
          type="button"
          variant="ghost"
          size="icon"
          disabled={isLoading}
          aria-label={t('relationship.refresh')}
          title={t('relationship.refresh')}
          onClick={loadChapters}
          className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface)] hover:text-[var(--aura-primary)]"
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </Button>
      }
    >
      <div className="mx-auto w-full max-w-5xl space-y-10">
        <header className="border-b border-[var(--aura-border)] pb-8">
          <div className="flex items-center gap-3 text-[var(--aura-primary)]">
            <Heart className="h-5 w-5" />
            <p className="text-sm font-medium">{t('relationship.eyebrow')}</p>
          </div>
          <h3 className="mt-4 max-w-3xl text-3xl font-semibold text-[var(--aura-text)]">
            {t('relationship.heading')}
          </h3>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--aura-text-muted)]">
            {t('relationship.description')}
          </p>
        </header>

        {isLoading ? (
          <div className="flex min-h-56 items-center justify-center gap-2 text-sm text-[var(--aura-text-muted)]">
            <Loader2 className="h-4 w-4 animate-spin text-[var(--aura-primary)]" />
            {t('relationship.loading')}
          </div>
        ) : chapters.length === 0 ? (
          <section className="border-y border-[var(--aura-border)] py-12">
            <p className="text-sm font-medium text-[var(--aura-primary)]">
              {t('relationship.emptyTitle')}
            </p>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-[var(--aura-text-muted)]">
              {t('relationship.emptyDescription')}
            </p>
          </section>
        ) : (
          <>
            {currentChapter ? (
              <section className="border-y border-[var(--aura-border)] py-7">
                <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                  <div className="max-w-3xl">
                    <p className="text-xs font-medium text-[var(--aura-primary)]">
                      {t('relationship.current')}
                    </p>
                    <h4 className="mt-2 text-2xl font-semibold text-[var(--aura-text)]">
                      {currentChapter.title}
                    </h4>
                    <p className="mt-3 text-sm leading-7 text-[var(--aura-text-muted)]">
                      {currentChapter.summary}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs text-[var(--aura-text-soft)]">
                    {formatChapterDate(currentChapter.startedAt, locale)}
                  </span>
                </div>
              </section>
            ) : null}

            {pastChapters.length > 0 ? (
              <section>
                <h4 className="text-lg font-semibold text-[var(--aura-text)]">
                  {t('relationship.past')}
                </h4>
                <ol className="mt-5 grid gap-4 md:grid-cols-2">
                  {pastChapters.map((chapter) => (
                    <li
                      key={chapter.id}
                      className="rounded-lg border border-[var(--aura-border)] bg-[var(--aura-surface)] p-5"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <h5 className="text-base font-semibold text-[var(--aura-text)]">
                          {chapter.title}
                        </h5>
                        <span className="shrink-0 text-xs text-[var(--aura-text-soft)]">
                          {formatChapterDate(chapter.startedAt, locale) ?? `#${chapter.sequenceNo}`}
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-7 text-[var(--aura-text-muted)]">
                        {chapter.summary}
                      </p>
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}
          </>
        )}
      </div>
    </AruaAppShell>
  )
}
