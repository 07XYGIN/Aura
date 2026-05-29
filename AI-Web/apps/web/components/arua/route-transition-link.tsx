'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { MouseEvent } from 'react'
import type { RouteTransitionLinkProps } from '@/types/arua'

export const AURA_ROUTE_LOADING_EVENT = 'aura-route-loading-start'

function getPathnameFromHref(href: RouteTransitionLinkProps['href']) {
  if (typeof href === 'string') {
    return href.split('?')[0]?.split('#')[0] ?? href
  }

  if (typeof href === 'object' && href.pathname) {
    return href.pathname
  }

  return ''
}

export function RouteTransitionLink({ href, onClick, ...props }: RouteTransitionLinkProps) {
  const pathname = usePathname()

  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event)

    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return
    }

    const nextPathname = getPathnameFromHref(href)

    if (!nextPathname || nextPathname === pathname) {
      return
    }

    window.dispatchEvent(new CustomEvent(AURA_ROUTE_LOADING_EVENT))
  }

  return <Link href={href} onClick={handleClick} {...props} />
}
