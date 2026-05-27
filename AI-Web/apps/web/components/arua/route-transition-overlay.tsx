'use client'

import { useEffect, useRef, useState } from 'react'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { RouteLoadingIndicator } from '@/components/arua/route-loading-indicator'
import { AURA_ROUTE_LOADING_EVENT } from '@/components/arua/route-transition-link'

const MINIMUM_OVERLAY_DURATION = 420

export function RouteTransitionOverlay() {
  const pathname = usePathname()
  const startedAtRef = useRef(0)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const handleStart = () => {
      startedAtRef.current = Date.now()
      setIsVisible(true)
    }

    window.addEventListener(AURA_ROUTE_LOADING_EVENT, handleStart)

    return () => {
      window.removeEventListener(AURA_ROUTE_LOADING_EVENT, handleStart)
    }
  }, [])

  useEffect(() => {
    if (!isVisible) {
      return
    }

    const elapsed = Date.now() - startedAtRef.current
    const timeout = window.setTimeout(
      () => setIsVisible(false),
      Math.max(0, MINIMUM_OVERLAY_DURATION - elapsed),
    )

    return () => window.clearTimeout(timeout)
  }, [isVisible, pathname])

  return (
    <div
      aria-hidden="true"
      className={cn(
        'pointer-events-none fixed inset-0 z-50 transition-opacity duration-300',
        isVisible ? 'opacity-100' : 'opacity-0',
      )}
    >
      <div className="absolute inset-0 bg-[color-mix(in_srgb,var(--aura-bg)_72%,transparent)] backdrop-blur-md" />
      <div className="absolute inset-x-0 top-0 h-1 overflow-hidden bg-[color-mix(in_srgb,var(--aura-primary)_10%,transparent)]">
        <span className="aura-loading-bar block h-full rounded-full bg-[linear-gradient(90deg,var(--aura-primary),var(--aura-secondary),var(--aura-primary))]" />
      </div>
      <div className="absolute inset-0 flex items-center justify-center px-6">
        <RouteLoadingIndicator
          compact
          label="Switching views"
          detail="Refreshing the next page shell"
        />
      </div>
    </div>
  )
}
