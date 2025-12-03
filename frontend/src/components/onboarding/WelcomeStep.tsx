import { Workflow, ShieldCheck, Zap, ArrowRight, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useOnboardingStore } from '@/stores'
import { INSTALLATION_GUIDE_URL } from '@/lib/constants'

export function WelcomeStep() {
  const setStep = useOnboardingStore((s) => s.setStep)

  return (
    <div className="flex flex-col gap-6">
      {/* Title */}
      <div className="flex flex-col gap-4">
        <h2 className="text-foreground text-2xl font-bold tracking-tight">Meet MagenticLite</h2>
        <p className="text-muted-foreground text-sm leading-relaxed">
          Big tasks. Small models. MagenticLite is the next generation of Magentic-UI — an agentic
          application redesigned to do more with less.
        </p>
      </div>

      {/* Value props */}
      <div className="flex flex-col gap-3">
        {VALUE_PROPS.map((vp) => (
          <div key={vp.title} className="flex gap-4">
            <vp.icon className="text-primary mt-0.5 size-7 shrink-0" />
            <div className="flex flex-col gap-1">
              <span className="text-foreground text-lg font-bold tracking-tight">{vp.title}</span>
              <span className="text-muted-foreground text-sm leading-relaxed">{vp.desc}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Bottom */}
      <div className="flex flex-col gap-6">
        <p className="text-muted-foreground text-sm font-medium">
          Let's get you set up in a few quick steps.
        </p>
        <div className="flex items-center justify-between">
          <Button variant="secondary" className="rounded-full" asChild>
            <a href={INSTALLATION_GUIDE_URL} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="size-4" />
              Installation Guide
            </a>
          </Button>
          <Button className="rounded-full" onClick={() => setStep('custom_endpoint')}>
            <ArrowRight className="size-4" />
            Get Started
          </Button>
        </div>
      </div>
    </div>
  )
}

const VALUE_PROPS = [
  {
    title: 'Works across the browser and your local file system',
    desc: 'Get real work done — from web research and form filling to file management, all in one workflow.',
    icon: Workflow,
  },
  {
    title: 'Keeps you in the loop and in control',
    desc: 'Steer, approve, or take over at any point. MagenticLite stops and checks in before taking critical actions.',
    icon: ShieldCheck,
  },
  {
    title: 'Built for small models, efficient by design',
    desc: 'Strong agentic performance without heavy compute — no frontier-scale models required.',
    icon: Zap,
  },
]
