'use client'

import { isValidElement, useCallback, useState, type ReactNode } from 'react'
import { Check, Copy } from 'lucide-react'
import ReactMarkdown, { type Components } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { copyTextToClipboard } from '@/lib/clipboard'

type ChatMessageContentProps = {
  content: string
  isUser?: boolean
}

type CodeBlockProps = {
  children: ReactNode
  className?: string
  isUser?: boolean
}

type CodeElementProps = {
  children?: ReactNode
  className?: string
}

const copiedResetDelayMs = 1400

export function ChatMessageContent({ content, isUser = false }: ChatMessageContentProps) {
  const components = markdownComponents(isUser)

  return (
    <div
      className={cn(
        'aura-markdown min-w-0 break-words text-sm leading-7',
        isUser ? 'aura-markdown-user' : 'aura-markdown-assistant',
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

function markdownComponents(isUser: boolean): Components {
  return {
    p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
    pre: ({ children }) => {
      if (isValidElement<CodeElementProps>(children)) {
        return (
          <CodeBlock className={children.props.className} isUser={isUser}>
            {children.props.children}
          </CodeBlock>
        )
      }

      return (
        <pre className="aura-scrollbar max-w-full overflow-x-auto rounded-lg p-3">
          {children}
        </pre>
      )
    },
    code: ({ children, className }) => {
      return (
        <code
          className={cn(
            'rounded px-1.5 py-0.5 font-mono text-[0.86em]',
            isUser ? 'bg-[#201733]/12 text-[#201733]' : 'bg-[var(--aura-surface-strong)]',
          )}
        >
          {children}
        </code>
      )
    },
    a: ({ children, href }) => (
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className={cn(
          'font-medium underline underline-offset-4',
          isUser ? 'text-[#201733]' : 'text-[var(--aura-primary)]',
        )}
      >
        {children}
      </a>
    ),
    ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
    ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
    li: ({ children }) => <li className="pl-1">{children}</li>,
    blockquote: ({ children }) => (
      <blockquote
        className={cn(
          'my-3 border-l-2 pl-3 italic',
          isUser ? 'border-[#201733]/25' : 'border-[var(--aura-border-strong)]',
        )}
      >
        {children}
      </blockquote>
    ),
    h1: ({ children }) => <h1 className="mt-1 mb-2 text-base font-semibold">{children}</h1>,
    h2: ({ children }) => <h2 className="mt-1 mb-2 text-[0.98rem] font-semibold">{children}</h2>,
    h3: ({ children }) => <h3 className="mt-1 mb-2 text-[0.94rem] font-semibold">{children}</h3>,
    table: ({ children }) => (
      <div className="my-3 max-w-full overflow-x-auto rounded-lg border border-[var(--aura-border)]">
        <table className="min-w-full border-collapse text-left text-xs">{children}</table>
      </div>
    ),
    th: ({ children }) => (
      <th className="border-b border-[var(--aura-border)] px-3 py-2 font-semibold">
        {children}
      </th>
    ),
    td: ({ children }) => <td className="border-t border-[var(--aura-border)] px-3 py-2">{children}</td>,
    hr: () => <hr className="my-3 border-[var(--aura-border)]" />,
  }
}

function CodeBlock({ children, className, isUser = false }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)
  const code = String(children)
  const language = /language-([\w-]+)/.exec(className ?? '')?.[1]

  const handleCopy = useCallback(async () => {
    try {
      await copyTextToClipboard(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), copiedResetDelayMs)
      toast.success('已复制代码', { position: 'top-center' })
    } catch {
      toast.error('复制失败', { position: 'top-center' })
    }
  }, [code])

  return (
    <div
      className={cn(
        'my-3 overflow-hidden rounded-lg border text-xs',
        isUser
          ? 'border-[#201733]/15 bg-[#201733]/8'
          : 'border-[var(--aura-border)] bg-[var(--aura-surface-solid)]/80',
      )}
    >
      <div
        className={cn(
          'flex h-9 items-center justify-between gap-3 border-b px-3',
          isUser ? 'border-[#201733]/12' : 'border-[var(--aura-border)]',
        )}
      >
        <span className="truncate font-mono text-[11px] opacity-70">{language ?? 'code'}</span>
        <button
          type="button"
          className={cn(
            'inline-flex h-7 w-7 items-center justify-center rounded-md transition',
            isUser ? 'hover:bg-[#201733]/10' : 'hover:bg-[var(--aura-surface-strong)]',
          )}
          aria-label="复制代码"
          title="复制代码"
          onClick={handleCopy}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
      <pre className="aura-scrollbar max-w-full overflow-x-auto p-3 leading-6">
        <code className={cn('font-mono', className)}>{code}</code>
      </pre>
    </div>
  )
}
