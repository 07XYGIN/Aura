'use client'

import { useEffect, useState } from 'react'
import { ImageIcon, X } from 'lucide-react'
import { getPythonApiBaseUrl } from '@/lib/python-request'
import { useUserStore } from '@/store/user'
import type { ChatAttachment } from '@/types/arua'
import { cn } from '@/lib/utils'

type ChatAttachmentPreviewProps = {
    attachment: ChatAttachment
    isUser?: boolean
}

export function ChatAttachmentPreview({ attachment, isUser = false }: ChatAttachmentPreviewProps) {
    const token = useUserStore((state) => state.token)
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [isOpen, setIsOpen] = useState(false)

    useEffect(() => {
        if (!attachment.id || !token) {
            setImageUrl(null)
            return
        }

        const controller = new AbortController()
        let objectUrl: string | null = null

        void fetch(
            `${getPythonApiBaseUrl()}/api/attachments/${encodeURIComponent(attachment.id)}/content`,
            {
                headers: { Authorization: `Bearer ${token}` },
                signal: controller.signal,
            },
        )
            .then(async (response) => {
                if (!response.ok) {
                    throw new Error('Attachment preview is unavailable')
                }
                objectUrl = URL.createObjectURL(await response.blob())
                setImageUrl(objectUrl)
            })
            .catch(() => {
                if (!controller.signal.aborted) {
                    setImageUrl(null)
                }
            })

        return () => {
            controller.abort()
            if (objectUrl) {
                URL.revokeObjectURL(objectUrl)
            }
        }
    }, [attachment.id, token])

    return (
        <>
            <div className="w-32 max-w-full">
                {imageUrl ? (
                    <button
                        type="button"
                        className="block aspect-square w-full overflow-hidden rounded-md border border-current/15 bg-black/5"
                        aria-label={`查看图片 ${attachment.fileName}`}
                        title={attachment.fileName}
                        onClick={() => setIsOpen(true)}
                    >
                        <img
                            src={imageUrl}
                            alt={attachment.fileName}
                            className="h-full w-full object-cover"
                        />
                    </button>
                ) : (
                    <div
                        className={cn(
                            'flex aspect-square w-full items-center justify-center rounded-md border border-dashed',
                            isUser
                                ? 'border-[#201733]/25 bg-[#201733]/8'
                                : 'border-[var(--aura-border)] bg-[var(--aura-surface-strong)]',
                        )}
                    >
                        <ImageIcon className="h-5 w-5 opacity-60" />
                    </div>
                )}
                <span
                    className="mt-1 block truncate text-[11px] leading-4 opacity-75"
                    title={attachment.fileName}
                >
                    {attachment.fileName}
                </span>
            </div>

            {isOpen && imageUrl ? (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-5"
                    role="dialog"
                    aria-modal="true"
                    aria-label={`查看图片 ${attachment.fileName}`}
                    onClick={() => setIsOpen(false)}
                >
                    <div
                        className="relative max-h-full max-w-full"
                        onClick={(event) => event.stopPropagation()}
                    >
                        <button
                            type="button"
                            className="absolute top-2 right-2 z-10 inline-flex h-9 w-9 items-center justify-center rounded-md bg-black/55 text-white transition hover:bg-black/75"
                            aria-label="关闭图片预览"
                            title="关闭"
                            onClick={() => setIsOpen(false)}
                        >
                            <X className="h-4 w-4" />
                        </button>
                        <img
                            src={imageUrl}
                            alt={attachment.fileName}
                            className="max-h-[88vh] max-w-[92vw] object-contain"
                        />
                    </div>
                </div>
            ) : null}
        </>
    )
}
