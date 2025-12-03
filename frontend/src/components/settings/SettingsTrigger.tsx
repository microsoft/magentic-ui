import { Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

/** Gear icon button that opens SettingsDialog. Can appear in multiple places. */
export function SettingsTrigger({ onClick }: { onClick: () => void }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="secondary"
          size="icon"
          className="size-9"
          aria-label="Settings"
          onClick={onClick}
        >
          <Settings className="size-5" />
        </Button>
      </TooltipTrigger>
      <TooltipContent side="left">Settings</TooltipContent>
    </Tooltip>
  )
}
