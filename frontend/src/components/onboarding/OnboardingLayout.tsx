import type { ReactNode } from 'react'

/** Full-screen onboarding layout: BrandPanel (left) + content (right) */
export function OnboardingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-background flex h-screen w-screen flex-col overflow-hidden min-[1160px]:flex-row">
      {/* Left: BrandPanel — hidden below 1160px */}
      <aside className="bg-card relative hidden w-[480px] shrink-0 flex-col items-center justify-center gap-4 px-12 min-[1160px]:flex">
        <img src="/magentic-logo.svg" alt="MagenticLite" className="h-[76px] w-[128px]" />
        <h1 className="text-foreground text-3xl tracking-tight">
          <span className="font-bold">Magentic</span>
          <span className="font-light">Lite</span>
        </h1>
        <p className="text-muted-foreground text-center text-base leading-relaxed">
          Built for small models.
          <br />
          Designed for real work.
        </p>
        <p className="text-muted-foreground absolute bottom-12 text-center text-sm">
          A research prototype from Microsoft AI Frontiers
        </p>
      </aside>

      {/* Narrow: top banner — shown below 1160px */}
      <div className="bg-sidebar border-sidebar-border flex h-[68px] w-full shrink-0 items-center justify-center gap-4 border-b px-5 min-[1160px]:hidden">
        <img src="/magentic-logo.svg" alt="MagenticLite" className="h-[33px] w-[55px]" />
        <span className="text-foreground text-2xl" style={{ letterSpacing: '-0.01em' }}>
          <span className="font-bold">Magentic</span>
          <span className="font-light">Lite</span>
        </span>
      </div>

      {/* Right: content area */}
      <main className="flex flex-1 flex-col items-center justify-center overflow-auto px-8 py-12 min-[1160px]:px-20">
        <div className="w-full max-w-[520px]">{children}</div>
      </main>
    </div>
  )
}
