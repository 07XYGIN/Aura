import type { Metadata } from 'next'
import './globals.css'
import 'katex/dist/katex.min.css'
import { ThemeProvider } from '@/components/theme-provider'
import { RouteTransitionOverlay } from '@/components/arua/route-transition-overlay'
import React from 'react'
import { Toaster } from '@/components/ui/sonner'
import { I18nProvider } from '@/lib/i18n'

export const metadata: Metadata = {
  title: 'Aura',
  description: 'Aura AI chat',
  icons: {
    icon: '/aura-mark.svg',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      className="h-full font-sans antialiased"
      suppressHydrationWarning
    >
      <body className="flex min-h-full flex-col overflow-x-hidden bg-[var(--aura-bg)] text-[var(--aura-text)]">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <I18nProvider>
            {children}
            <Toaster />
            <RouteTransitionOverlay />
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
