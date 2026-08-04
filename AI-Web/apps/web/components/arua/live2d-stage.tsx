'use client'

import { useEffect, useRef, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Live2DPresence } from '@/types/arua'

const PIXI_URL = 'https://cdn.jsdelivr.net/npm/pixi.js@6.5.10/dist/browser/pixi.min.js'
const LIVE2D_CUBISM2_URL =
    'https://cdn.jsdelivr.net/gh/dylanNew/live2d/webgl/Live2D/lib/live2d.min.js'
const LIVE2D_CUBISM4_URL = 'https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js'
const LIVE2D_DISPLAY_URL =
    'https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/index.min.js'
const DEFAULT_MODEL_URL =
    process.env.NEXT_PUBLIC_LIVE2D_MODEL_URL ??
    'https://cdn.jsdelivr.net/gh/guansss/pixi-live2d-display/test/assets/shizuku/shizuku.model.json'
const MODEL_SCALE = Number(process.env.NEXT_PUBLIC_LIVE2D_MODEL_SCALE ?? '')
const EXPRESSION_BY_PRESENCE: Record<Live2DPresence['expression'], string | undefined> = {
    calm: process.env.NEXT_PUBLIC_LIVE2D_CALM_EXPRESSION,
    warm: process.env.NEXT_PUBLIC_LIVE2D_WARM_EXPRESSION,
    playful: process.env.NEXT_PUBLIC_LIVE2D_PLAYFUL_EXPRESSION,
    thinking: process.env.NEXT_PUBLIC_LIVE2D_THINKING_EXPRESSION,
    soft: process.env.NEXT_PUBLIC_LIVE2D_SOFT_EXPRESSION,
    concerned: process.env.NEXT_PUBLIC_LIVE2D_CONCERNED_EXPRESSION,
}
const MOTION_BY_PRESENCE: Record<Live2DPresence['motion'], string | undefined> = {
    idle: process.env.NEXT_PUBLIC_LIVE2D_IDLE_MOTION_GROUP,
    acknowledge: process.env.NEXT_PUBLIC_LIVE2D_ACKNOWLEDGE_MOTION_GROUP,
    wave: process.env.NEXT_PUBLIC_LIVE2D_WAVE_MOTION_GROUP,
}
const DEFAULT_PRESENCE: Live2DPresence = { expression: 'calm', motion: 'idle', intensity: 0 }

type Live2DStageProps = {
    className?: string
    isActive?: boolean
    emotionLabel?: string | null
    presence?: Live2DPresence | null
    labels: {
        presence: string
        subtitle: string
        ready: string
        loading: string
        play: string
        unavailable: string
    }
}

type PixiApplication = {
    stage: {
        addChild: (child: Live2DDisplayModel) => void
        removeChild: (child: Live2DDisplayModel) => void
    }
    renderer: {
        resize: (width: number, height: number) => void
    }
    destroy: (
        removeView?: boolean,
        options?: { children?: boolean; texture?: boolean; baseTexture?: boolean },
    ) => void
}

type Live2DDisplayModel = {
    width: number
    height: number
    x: number
    y: number
    scale: { set: (scale: number) => void }
    on: (eventName: string, handler: () => void) => void
    motion?: (group?: string, index?: number) => void
    expression?: (expression?: string | number) => void
    destroy?: () => void
}

type PixiNamespace = {
    Application: new (options: {
        view: HTMLCanvasElement
        width: number
        height: number
        antialias: boolean
        autoDensity: boolean
        backgroundAlpha: number
        resolution: number
    }) => PixiApplication
    live2d?: {
        Live2DModel?: {
            from: (url: string) => Promise<Live2DDisplayModel>
        }
    }
}

declare global {
    interface Window {
        PIXI?: PixiNamespace
    }
}

let live2dRuntimePromise: Promise<void> | null = null

const loadScript = (src: string) =>
    new Promise<void>((resolve, reject) => {
        const existing = document.querySelector<HTMLScriptElement>(`script[src="${src}"]`)
        if (existing?.dataset.loaded === 'true') {
            resolve()
            return
        }

        const script = existing ?? document.createElement('script')
        script.src = src
        script.async = true
        script.dataset.live2dRuntime = 'true'
        script.addEventListener('load', () => {
            script.dataset.loaded = 'true'
            resolve()
        })
        script.addEventListener('error', () => reject(new Error(`Failed to load ${src}`)))

        if (!existing) {
            document.head.appendChild(script)
        }
    })

const loadLive2DRuntime = () => {
    live2dRuntimePromise ??= Promise.all([
        loadScript(PIXI_URL),
        loadScript(LIVE2D_CUBISM2_URL),
        loadScript(LIVE2D_CUBISM4_URL),
    ])
        .then(() => loadScript(LIVE2D_DISPLAY_URL))
        .then(() => undefined)

    return live2dRuntimePromise
}

export function Live2DStage({
    className,
    isActive = false,
    emotionLabel,
    presence,
    labels,
}: Live2DStageProps) {
    const containerRef = useRef<HTMLDivElement>(null)
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const modelRef = useRef<Live2DDisplayModel | null>(null)
    const presenceRef = useRef<Live2DPresence>(presence ?? DEFAULT_PRESENCE)
    const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
    const [isExpressionPlaying, setIsExpressionPlaying] = useState(false)

    const triggerPresence = (nextPresence = presenceRef.current) => {
        const model = modelRef.current
        try {
            const expression = EXPRESSION_BY_PRESENCE[nextPresence.expression]
            const motion = MOTION_BY_PRESENCE[nextPresence.motion]
            if (expression) {
                model?.expression?.(expression)
            }
            if (motion) {
                model?.motion?.(motion)
            }
        } catch {
            // Assets may not define every optional expression or motion group.
        }
        if (nextPresence.intensity > 0) {
            setIsExpressionPlaying(true)
            window.setTimeout(() => setIsExpressionPlaying(false), 900)
        }
    }

    useEffect(() => {
        let disposed = false
        let app: PixiApplication | null = null
        let resizeObserver: ResizeObserver | null = null

        const fitModel = () => {
            const container = containerRef.current
            const model = modelRef.current
            if (!container || !model || !app) {
                return
            }

            const rect = container.getBoundingClientRect()
            const width = Math.max(320, rect.width)
            const height = Math.max(420, rect.height)

            app.renderer.resize(width, height)
            const autoScale = Math.min(width / model.width, height / model.height) * 0.28
            const scale = Number.isFinite(MODEL_SCALE) && MODEL_SCALE > 0 ? MODEL_SCALE : autoScale
            model.scale.set(Number.isFinite(scale) ? scale : 0.1)
            model.x = (width - model.width) * 0.5
            model.y = height - model.height + height * 0.02
        }

        const mountModel = async () => {
            const canvas = canvasRef.current
            const container = containerRef.current
            if (!canvas || !container) {
                return
            }

            try {
                await loadLive2DRuntime()

                if (disposed || !window.PIXI?.live2d?.Live2DModel) {
                    return
                }

                const rect = container.getBoundingClientRect()
                app = new window.PIXI.Application({
                    view: canvas,
                    width: Math.max(320, rect.width),
                    height: Math.max(420, rect.height),
                    antialias: true,
                    autoDensity: true,
                    backgroundAlpha: 0,
                    resolution: Math.min(window.devicePixelRatio || 1, 2),
                })

                const model = await window.PIXI.live2d.Live2DModel.from(DEFAULT_MODEL_URL)
                if (disposed) {
                    model.destroy?.()
                    return
                }

                model.on('hit', () => {
                    triggerPresence()
                })

                modelRef.current = model
                app.stage.addChild(model)
                fitModel()

                resizeObserver = new ResizeObserver(fitModel)
                resizeObserver.observe(container)
                setStatus('ready')
            } catch {
                setStatus('error')
            }
        }

        void mountModel()

        return () => {
            disposed = true
            resizeObserver?.disconnect()
            if (app && modelRef.current) {
                app.stage.removeChild(modelRef.current)
            }
            modelRef.current?.destroy?.()
            modelRef.current = null
            app?.destroy(true, { children: true, texture: true, baseTexture: true })
        }
    }, [])

    useEffect(() => {
        if (!isActive || status !== 'ready') {
            return
        }

        modelRef.current?.motion?.('Tap')
    }, [isActive, status])

    useEffect(() => {
        presenceRef.current = presence ?? DEFAULT_PRESENCE
        if (status === 'ready') {
            triggerPresence(presenceRef.current)
        }
    }, [presence, status])

    return (
        <div
            ref={containerRef}
            className={cn(
                'relative isolate min-h-[24rem] overflow-hidden rounded-[1.5rem] border border-[var(--aura-border)] bg-[radial-gradient(circle_at_52%_26%,rgba(92,148,132,0.18),transparent_30%),linear-gradient(180deg,color-mix(in_srgb,var(--aura-surface-solid)_82%,transparent),rgba(12,18,24,0.16))]',
                className,
            )}
        >
            <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.08),transparent_34%,rgba(72,92,112,0.12))]" />
            <div className="pointer-events-none absolute inset-x-6 top-6 z-10 flex items-center justify-between gap-3">
                <div className="min-w-0">
                    <p className="text-xs font-medium tracking-[0.28em] text-[var(--aura-text-soft)] uppercase">
                        {labels.presence}
                    </p>
                    <h2 className="mt-1 truncate text-2xl font-semibold text-[var(--aura-text)]">
                        Arua
                    </h2>
                    <p className="mt-1 truncate text-xs text-[var(--aura-text-muted)]">
                        {labels.subtitle}
                    </p>
                </div>
                <div className="inline-flex items-center gap-2 rounded-full border border-[var(--aura-border)] bg-[var(--aura-surface)] px-3 py-1.5 text-xs text-[var(--aura-text-muted)]">
                    <span
                        className={cn(
                            'h-2 w-2 rounded-full',
                            status === 'ready'
                                ? 'bg-[var(--aura-primary)]'
                                : 'bg-[var(--aura-tertiary)]',
                        )}
                    />
                    <span>{status === 'ready' ? (emotionLabel ?? labels.ready) : labels.loading}</span>
                </div>
            </div>

            <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />

            <div
                className={cn(
                    'pointer-events-none absolute top-[34%] left-1/2 z-10 h-16 w-40 -translate-x-1/2 rounded-full bg-white/85 opacity-0 blur-[18px] transition-opacity duration-150',
                    isExpressionPlaying && 'opacity-80',
                )}
            />

            <button
                type="button"
                className="absolute top-20 right-6 z-20 inline-flex h-9 w-9 items-center justify-center rounded-full border border-[var(--aura-border)] bg-[var(--aura-surface)] text-[var(--aura-text-muted)] shadow-[0_14px_34px_-26px_var(--aura-glow)] transition hover:bg-[var(--aura-surface-strong)] hover:text-[var(--aura-primary)]"
                aria-label={labels.play}
                title={labels.play}
                onClick={() => triggerPresence()}
            >
                <Sparkles className="h-4 w-4" />
            </button>

            {status === 'error' ? (
                <div className="absolute inset-0 flex items-center justify-center px-8 text-center text-sm leading-6 text-[var(--aura-text-muted)]">
                    {labels.unavailable}
                </div>
            ) : null}
        </div>
    )
}
