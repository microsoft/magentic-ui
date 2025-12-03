/** Two number inputs that bind to `MagenticUIConfig.harness_config` max_rounds caps. */
import { useState } from 'react'
import {
  useAgentSettings,
  useUpdateAgentSettings,
  type AgentSettings as AgentSettingsValue,
} from '@/api'
import { Input } from '@/components/ui/input'

const MIN_ROUNDS = 1
const MAX_ROUNDS = 1000

export function AgentMaxRoundsSettings() {
  const { data, isLoading, error } = useAgentSettings()

  if (isLoading) {
    return <p className="text-muted-foreground text-sm">Loading agent settings…</p>
  }
  if (error || !data) {
    return (
      <p className="text-destructive text-sm">
        Failed to load agent max-rounds. Reopen this dialog to retry.
      </p>
    )
  }

  // Remount the form when server values change so local input state re-initializes.
  const formKey = `${data.orchestrator.max_rounds}-${data.web_surfer.max_rounds}`
  return <AgentMaxRoundsForm key={formKey} initial={data} />
}

interface AgentMaxRoundsFormProps {
  initial: AgentSettingsValue
}

function AgentMaxRoundsForm({ initial }: AgentMaxRoundsFormProps) {
  const updateMutation = useUpdateAgentSettings()
  const [orchestratorInput, setOrchestratorInput] = useState(() =>
    String(initial.orchestrator.max_rounds)
  )
  const [webSurferInput, setWebSurferInput] = useState(() => String(initial.web_surfer.max_rounds))

  const commit = (
    raw: string,
    current: number,
    setLocal: (next: string) => void,
    apply: (next: number) => AgentSettingsValue
  ) => {
    const trimmed = raw.trim()
    // Reject anything that isn't a plain decimal integer literal so
    // "5x", "3.9", and "1e3" can't slip past Number() and let the
    // displayed text diverge from the committed value.
    if (!/^-?\d+$/.test(trimmed)) {
      setLocal(String(current))
      return
    }
    const parsed = Number(trimmed)
    if (parsed < MIN_ROUNDS || parsed > MAX_ROUNDS) {
      setLocal(String(current))
      return
    }
    if (parsed === current) return
    setLocal(String(parsed))
    updateMutation.mutate(apply(parsed))
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Orchestrator max rounds */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-col">
          <label htmlFor="orchestrator-max-rounds" className="text-sm font-bold">
            Orchestrator Max Rounds
          </label>
          <span className="text-muted-foreground text-xs">
            How many rounds the orchestrator may take before generating a best-effort final answer.
            Range: {MIN_ROUNDS}–{MAX_ROUNDS}.
          </span>
        </div>
        <Input
          id="orchestrator-max-rounds"
          type="number"
          min={MIN_ROUNDS}
          max={MAX_ROUNDS}
          step={1}
          inputMode="numeric"
          value={orchestratorInput}
          onChange={(e) => setOrchestratorInput(e.target.value)}
          onBlur={() =>
            commit(
              orchestratorInput,
              initial.orchestrator.max_rounds,
              setOrchestratorInput,
              (next) => ({
                ...initial,
                orchestrator: { ...initial.orchestrator, max_rounds: next },
              })
            )
          }
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              ;(e.target as HTMLInputElement).blur()
            }
          }}
          disabled={updateMutation.isPending}
          className="w-24 text-right"
        />
      </div>

      <div className="border-border border-t" />

      {/* Browser use max rounds */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-col">
          <label htmlFor="web-surfer-max-rounds" className="text-sm font-bold">
            Browser Use Max Actions
          </label>
          <span className="text-muted-foreground text-xs">
            How many actions the browser agent may take before pausing to ask whether to keep going.
            Range: {MIN_ROUNDS}–{MAX_ROUNDS}.
          </span>
        </div>
        <Input
          id="web-surfer-max-rounds"
          type="number"
          min={MIN_ROUNDS}
          max={MAX_ROUNDS}
          step={1}
          inputMode="numeric"
          value={webSurferInput}
          onChange={(e) => setWebSurferInput(e.target.value)}
          onBlur={() =>
            commit(webSurferInput, initial.web_surfer.max_rounds, setWebSurferInput, (next) => ({
              ...initial,
              web_surfer: { ...initial.web_surfer, max_rounds: next },
            }))
          }
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              ;(e.target as HTMLInputElement).blur()
            }
          }}
          disabled={updateMutation.isPending}
          className="w-24 text-right"
        />
      </div>

      {updateMutation.isError && (
        <p className="text-destructive text-xs">
          {(updateMutation.error as Error)?.message ?? 'Failed to save settings'}
        </p>
      )}
    </div>
  )
}
