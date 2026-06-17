'use client'

import { useCallback, useEffect, useState } from 'react'
import { BrainCircuit, Loader2, Sparkles, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { aura, type AuraMemoryItem } from '@/apis/aura'
import { AruaAppShell } from '@/components/arua/app-shell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardTitle } from '@/components/ui/card'
import { useI18n } from '@/lib/i18n'

const PAGE_SIZE = 50

const getMemoryTitle = (memory: AuraMemoryItem, fallback: string) => {
  const title = memory.metadata?.title
  return typeof title === 'string' && title.trim() ? title : fallback
}

const getMemoryContent = (memory: AuraMemoryItem) => {
  const metadataContent = memory.metadata?.content
  if (typeof metadataContent === 'string' && metadataContent.trim()) {
    return metadataContent
  }

  return memory.page_content ?? ''
}

const getMemoryTime = (memory: AuraMemoryItem) => {
  const createTime = memory.metadata?.create_time
  return typeof createTime === 'string' ? createTime : null
}

export function AruaMemoriesScreen() {
  const { t } = useI18n()
  const [memories, setMemories] = useState<AuraMemoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [deletingMemoryId, setDeletingMemoryId] = useState<string | null>(null)
  const [isClearing, setIsClearing] = useState(false)

  const loadMemories = useCallback(async () => {
    setIsLoading(true)

    try {
      const response = await aura.getMemories(1, PAGE_SIZE)
      const memoryPage = response.data
      setMemories(memoryPage?.items ?? [])
      setTotal(memoryPage?.total ?? 0)
    } catch {
      toast.error(t('memories.loadFailed'), {
        description: t('chat.tryAgain'),
        position: 'top-center',
      })
    } finally {
      setIsLoading(false)
    }
  }, [t])

  useEffect(() => {
    loadMemories()
  }, [loadMemories])

  const handleDeleteMemory = async (memoryId: string) => {
    if (deletingMemoryId || isClearing) {
      return
    }

    setDeletingMemoryId(memoryId)

    try {
      await aura.deleteMemory(memoryId)
      setMemories((currentMemories) =>
        currentMemories.filter((memory) => memory.id !== memoryId),
      )
      setTotal((currentTotal) => Math.max(currentTotal - 1, 0))
      toast.success(t('memories.deleted'), {
        position: 'top-center',
      })
    } catch {
      toast.error(t('memories.deleteFailed'), {
        description: t('chat.tryAgain'),
        position: 'top-center',
      })
    } finally {
      setDeletingMemoryId(null)
    }
  }

  const handleClearMemories = async () => {
    if (isClearing || memories.length === 0) {
      return
    }

    setIsClearing(true)

    try {
      await aura.clearMemories()
      setMemories([])
      setTotal(0)
      toast.success(t('memories.cleared'), {
        position: 'top-center',
      })
    } catch {
      toast.error(t('memories.clearFailed'), {
        description: t('chat.tryAgain'),
        position: 'top-center',
      })
    } finally {
      setIsClearing(false)
    }
  }

  const totalText = t('memories.total').replace('{count}', String(total))

  return (
    <AruaAppShell
      active="memories"
      title={
        <h2 className="text-2xl font-semibold tracking-tight text-[var(--aura-primary)]">
          {t('memories.title')}
        </h2>
      }
    >
      <div className="mx-auto w-full max-w-7xl space-y-8">
        <Card className="rounded-[2rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_86%,transparent)] py-0 shadow-[0_28px_72px_-54px_var(--aura-glow)]">
          <CardContent className="p-6 sm:p-8">
            <div className="flex flex-col gap-4 border-b border-[var(--aura-border)] pb-5 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-[11px] tracking-[0.3em] text-[var(--aura-text-soft)] uppercase">
                  {totalText}
                </p>
                <h4 className="mt-3 text-2xl font-semibold text-[var(--aura-text)]">
                  {t('memories.heading')}
                </h4>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  disabled={isLoading}
                  className="rounded-full border-[var(--aura-border)] bg-transparent px-5 text-xs tracking-[0.24em] text-[var(--aura-text)] uppercase disabled:opacity-60"
                  onClick={loadMemories}
                >
                  {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {t('memories.refresh')}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="lg"
                  disabled={isLoading || isClearing || memories.length === 0}
                  className="rounded-full px-5 text-xs tracking-[0.24em] text-[var(--aura-text-muted)] uppercase hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                  onClick={handleClearMemories}
                >
                  <Trash2 className="h-4 w-4" />
                  {t('memories.clearAll')}
                </Button>
              </div>
            </div>

            {isLoading ? (
              <div className="flex min-h-44 items-center justify-center gap-2 text-sm text-[var(--aura-text-muted)]">
                <Loader2 className="h-4 w-4 animate-spin text-[var(--aura-primary)]" />
                {t('memories.loading')}
              </div>
            ) : memories.length > 0 ? (
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {memories.map((memory) => {
                  const title = getMemoryTitle(memory, t('memories.untitled'))
                  const content = getMemoryContent(memory)
                  const createTime = getMemoryTime(memory)

                  return (
                    <article
                      key={memory.id}
                      className="group/memory rounded-2xl border border-[var(--aura-border)] bg-[var(--aura-surface)] p-4 shadow-[0_18px_42px_-38px_var(--aura-glow)]"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 text-[var(--aura-primary)]">
                            <BrainCircuit className="h-4 w-4 shrink-0" />
                            <h5 className="truncate text-sm font-semibold text-[var(--aura-text)]">
                              {title}
                            </h5>
                          </div>
                          {createTime ? (
                            <p className="mt-1 text-xs text-[var(--aura-text-soft)]">
                              {createTime}
                            </p>
                          ) : null}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          disabled={deletingMemoryId === memory.id || isClearing}
                          className="rounded-full text-[var(--aura-text-muted)] hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                          aria-label={t('memories.delete')}
                          title={t('memories.delete')}
                          onClick={() => handleDeleteMemory(memory.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      <p className="mt-3 line-clamp-4 text-sm leading-7 text-[var(--aura-text-muted)]">
                        {content}
                      </p>
                      <p className="mt-3 truncate text-xs text-[var(--aura-text-soft)]">
                        {memory.id}
                      </p>
                    </article>
                  )
                })}
              </div>
            ) : (
              <div className="flex min-h-44 flex-col justify-center">
                <p className="text-[11px] tracking-[0.3em] text-[var(--aura-text-soft)] uppercase">
                  {t('memories.emptyEyebrow')}
                </p>
                <h4 className="mt-3 text-2xl font-semibold text-[var(--aura-text)]">
                  {t('memories.emptyTitle')}
                </h4>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-[var(--aura-text-muted)]">
                  {t('memories.emptyDescription')}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AruaAppShell>
  )
}
