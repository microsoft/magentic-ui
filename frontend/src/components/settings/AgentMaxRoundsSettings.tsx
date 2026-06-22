/** Two number inputs that bind to `MagenticUIConfig.harness_config` max_rounds caps. */
import { useState } from 'react'
import {
  useAgentSettings,
  useUpdateAgentSettings,
  type AgentSettings as AgentSettingsValue,
} from '@/api'
import { Input } from '@/components/ui/input'
import { useBackendHealthStore } from '@/stores'

const MIN_ROUNDS = 1
const MAX_ROUNDS = 1000

export function AgentMaxRoundsSettings() {
  const { data } = useAgentSettings()

  // Remount when server values change so input state re-initializes.
  // When data is null (loading or fetch failed) the form renders
  // disabled with empty inputs.
  const formKey = data ? `${data.orchestrator.max_rounds}-${data.web_surfer.max_rounds}` : 'no-data'
  return <AgentMaxRoundsForm key={formKey} initial={data ?? null} />
}

interface AgentMaxRoundsFormProps {
  /** Server-loaded values, or null when not yet loaded. */
  initial: AgentSettingsValue | null
}

function AgentMaxRoundsForm({ initial }: AgentMaxRoundsFormProps) {
  const updateMutation = useUpdateAgentSettings()
  const reachable = useBackendHealthStore((s) => s.reachable)
  const disabled = updateMutation.isPending || !reachable || initial === null
  const [orchestratorInput, setOrchestratorInput] = useState(() =>
    initial ? String(initial.orchestrator.max_rounds) : ''
  )
  const [webSurferInput, setWebSurferInput] = useState(() =>
    initial ? String(initial.web_surfer.max_rounds) : ''
  )

  const commit = (
    raw: string,
    current: number,
    setLocal: (next: string) => void,
    apply: (next: number) => AgentSettingsValue
  ) => {
    if (initial === null) return
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
          onBlur={() => {
            if (!initial) return
            commit(
              orchestratorInput,
              initial.orchestrator.max_rounds,
              setOrchestratorInput,
              (next) => ({
                ...initial,
                orchestrator: { ...initial.orchestrator, max_rounds: next },
              })
            )
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              ;(e.target as HTMLInputElement).blur()
            }
          }}
          disabled={disabled}
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
          onBlur={() => {
            if (!initial) return
            commit(webSurferInput, initial.web_surfer.max_rounds, setWebSurferInput, (next) => ({
              ...initial,
              web_surfer: { ...initial.web_surfer, max_rounds: next },
            }))
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              ;(e.target as HTMLInputElement).blur()
            }
          }}
          disabled={disabled}
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
