import { MessageSquareText, SendHorizontal } from 'lucide-react'
import { AruaAppShell } from '@/components/arua/app-shell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'

export function AruaChatScreen() {
  return (
    <AruaAppShell
      active="chat"
      showDefaultAction={false}
      title={<h2 className="text-2xl font-semibold tracking-tight text-[var(--aura-primary)]">Chat</h2>}
      contentClassName="flex"
    >
      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col">
        <Card className="flex flex-1 rounded-[2rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_84%,transparent)] py-0 shadow-[0_30px_70px_-48px_var(--aura-glow)]">
          <CardHeader className="border-b border-[var(--aura-border)] px-6 py-5 sm:px-8">
            <p className="text-[11px] uppercase tracking-[0.3em] text-[var(--aura-text-soft)]">
              Conversation
            </p>
            <CardTitle className="mt-1 text-lg font-semibold text-[var(--aura-text)]">
              Chat-only workspace
            </CardTitle>
            <CardDescription className="text-sm leading-6 text-[var(--aura-text-muted)]">
              The conversation stream is intentionally empty until the backend chat service
              is connected.
            </CardDescription>
          </CardHeader>

          <CardContent className="flex flex-1 flex-col px-4 py-6 sm:px-6">
            <div className="flex flex-1 items-center justify-center rounded-[1.75rem] border border-dashed border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface)_72%,transparent)] p-8">
              <div className="max-w-md text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.6rem] bg-[var(--aura-primary-soft)] shadow-[0_18px_36px_-28px_var(--aura-glow)]">
                  <MessageSquareText className="h-7 w-7 text-[var(--aura-primary)]" />
                </div>
                <h3 className="mt-6 text-xl font-semibold text-[var(--aura-text)]">
                  No messages yet
                </h3>
                <p className="mt-3 text-sm leading-7 text-[var(--aura-text-muted)]">
                  Message history, assistant replies, and delivery states will render here
                  after the chat API is connected.
                </p>
              </div>
            </div>

            <div className="mt-6">
              <Card className="rounded-[1.75rem] border-[var(--aura-border)] bg-[color-mix(in_srgb,var(--aura-surface-solid)_88%,transparent)] py-0 shadow-[0_24px_60px_-42px_var(--aura-glow)] backdrop-blur-xl">
                <CardContent className="p-4">
                  <Textarea
                    rows={4}
                    placeholder="Type your message here..."
                    className="aura-scrollbar min-h-28 resize-none border-0 bg-transparent px-1 py-1 text-sm leading-7 text-[var(--aura-text)] shadow-none ring-0 focus-visible:border-0 focus-visible:ring-0"
                  />
                  <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-xs uppercase tracking-[0.24em] text-[var(--aura-text-soft)]">
                      Sending will be enabled after backend integration
                    </p>
                    <Button
                      type="button"
                      size="lg"
                      disabled
                      className="rounded-full bg-[linear-gradient(135deg,var(--aura-primary),var(--aura-secondary))] px-5 text-sm font-semibold text-[#201733] opacity-60 shadow-[0_22px_36px_-24px_var(--aura-glow)] disabled:pointer-events-none disabled:opacity-60"
                    >
                      <SendHorizontal className="h-4 w-4" />
                      Send
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>
      </div>
    </AruaAppShell>
  )
}
