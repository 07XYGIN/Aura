import { LoginForm } from '@/components/login/login-from'
import { RouteTransitionLink } from '@/components/arua/route-transition-link'

export default function LoginPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-16">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute top-[-8rem] left-[-12rem] h-96 w-96 rounded-full bg-[var(--aura-gradient-start)] blur-3xl" />
        <div className="absolute right-[-8rem] bottom-[-10rem] h-[26rem] w-[26rem] rounded-full bg-[var(--aura-gradient-end)] blur-3xl" />
      </div>
      <div className="relative z-10 flex w-full max-w-lg flex-col gap-10">
        <RouteTransitionLink href="/" className="flex flex-col items-center gap-3 text-center">
          <h1 className="text-5xl font-bold tracking-tight text-[var(--aura-primary)] sm:text-6xl">
            Arua
          </h1>
          <p className="text-xl text-[var(--aura-text-muted)]">Always here for you</p>
        </RouteTransitionLink>
        <LoginForm />
      </div>
    </main>
  )
}
