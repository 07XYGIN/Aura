import { RouteLoadingIndicator } from '@/components/arua/route-loading-indicator'

export default function Loading() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-16">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute top-[-8rem] left-[-12rem] h-96 w-96 rounded-full bg-[var(--aura-gradient-start)] blur-3xl" />
        <div className="absolute right-[-8rem] bottom-[-10rem] h-[24rem] w-[24rem] rounded-full bg-[var(--aura-gradient-end)] blur-3xl" />
      </div>
      <div className="relative z-10 w-full max-w-md">
        <RouteLoadingIndicator
          label="Loading page"
          detail="Preparing the next Arua workspace view"
        />
      </div>
    </main>
  )
}
