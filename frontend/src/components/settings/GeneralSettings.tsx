/** Per-user toggles plus per-agent max_rounds caps. */
import { Switch } from '@/components/ui/switch'
import { useUIStore } from '@/stores'
import { AgentMaxRoundsSettings } from './AgentMaxRoundsSettings'

export function GeneralSettings() {
  const darkMode = useUIStore((s) => s.darkMode)
  const setDarkMode = useUIStore((s) => s.setDarkMode)
  const showReasoningDetails = useUIStore((s) => s.showReasoningDetails)
  const setShowReasoningDetails = useUIStore((s) => s.setShowReasoningDetails)
  const showToolCallDetails = useUIStore((s) => s.showToolCallDetails)
  const setShowToolCallDetails = useUIStore((s) => s.setShowToolCallDetails)
  const showBrowserActionDetails = useUIStore((s) => s.showBrowserActionDetails)
  const setShowBrowserActionDetails = useUIStore((s) => s.setShowBrowserActionDetails)
  const wrapMode = useUIStore((s) => s.wrapMode)
  const setWrapMode = useUIStore((s) => s.setWrapMode)

  return (
    <div className="flex flex-col gap-3">
      {/* Dark Mode */}
      <div className="flex items-center justify-between">
        <div className="flex flex-col">
          <label htmlFor="dark-mode" className="text-sm font-bold">
            Dark Mode
          </label>
          <span className="text-muted-foreground text-xs">
            Use the dark color theme across the app
          </span>
        </div>
        <Switch id="dark-mode" checked={darkMode} onCheckedChange={setDarkMode} />
      </div>

      <div className="border-border border-t" />

      {/* Show Reasoning Details */}
      <div className="flex items-center justify-between">
        <div className="flex flex-col">
          <label htmlFor="show-reasoning" className="text-sm font-bold">
            Show Reasoning Details
          </label>
          <span className="text-muted-foreground text-xs">
            Expand reasoning sections by default
          </span>
        </div>
        <Switch
          id="show-reasoning"
          checked={showReasoningDetails}
          onCheckedChange={setShowReasoningDetails}
        />
      </div>

      <div className="border-border border-t" />

      {/* Show Tool Call Details */}
      <div className="flex items-center justify-between">
        <div className="flex flex-col">
          <label htmlFor="show-tool-calls" className="text-sm font-bold">
            Show Tool Call Details
          </label>
          <span className="text-muted-foreground text-xs">
            Expand tool call sections by default
          </span>
        </div>
        <Switch
          id="show-tool-calls"
          checked={showToolCallDetails}
          onCheckedChange={setShowToolCallDetails}
        />
      </div>

      <div className="border-border border-t" />

      {/* Show Browser Action Details */}
      <div className="flex items-center justify-between">
        <div className="flex flex-col">
          <label htmlFor="show-browser-actions" className="text-sm font-bold">
            Detailed Browser Actions
          </label>
          <span className="text-muted-foreground text-xs">
            Show reasoning and action content under each browser step
          </span>
        </div>
        <Switch
          id="show-browser-actions"
          checked={showBrowserActionDetails}
          onCheckedChange={setShowBrowserActionDetails}
        />
      </div>

      <div className="border-border border-t" />

      {/* Wrap Mode */}
      <div className="flex items-center justify-between">
        <div className="flex flex-col">
          <label htmlFor="wrap-mode" className="text-sm font-bold">
            Line Wrap
          </label>
          <span className="text-muted-foreground text-xs">
            Wrap long lines in code and output blocks
          </span>
        </div>
        <Switch id="wrap-mode" checked={wrapMode} onCheckedChange={setWrapMode} />
      </div>

      <div className="border-border border-t" />

      {/* Per-agent max_rounds caps (server-persisted) */}
      <AgentMaxRoundsSettings />
    </div>
  )
}
