import { type ReactNode } from 'react'
import { type ModelEndpointConfig } from '@/stores/onboardingStore'
import { TriangleAlert } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { API_KEY_MASKED } from '@/api/onboarding'

interface ModelConfigCardProps {
  /** Display name shown as card title */
  name: string
  /** Current field values */
  config: ModelEndpointConfig
  /** Field change handler */
  onChange: (config: Partial<ModelEndpointConfig>) => void
  /** Visual state */
  state?: 'default' | 'filled' | 'error'
  /** Whether inputs are disabled */
  disabled?: boolean
  /** Custom placeholders per field */
  placeholders?: Partial<Record<keyof ModelEndpointConfig, string>>
  /**
   * When provided, renders a checkbox in the card header. The card body is
   * rendered grayed-out and inputs disabled when `enabled` is false.
   */
  enabled?: boolean
  /** Called when the header checkbox is toggled. Required if `enabled` is set. */
  onEnabledChange?: (enabled: boolean) => void
  /** Description text rendered under the title */
  description?: ReactNode
  /** Optional row rendered below the description (e.g. recommended model link) */
  recommendation?: ReactNode
}

const DEFAULT_PLACEHOLDERS: Record<keyof ModelEndpointConfig, string> = {
  endpointUrl: 'e.g. http://localhost:6000/v1',
  modelName: 'e.g. magenticbrain-v1',
  apiKey: '',
}

const FIELDS: { key: keyof ModelEndpointConfig; label: string }[] = [
  { key: 'endpointUrl', label: 'Endpoint URL' },
  { key: 'modelName', label: 'Model Name' },
  { key: 'apiKey', label: 'API Key (optional)' },
]

export function ModelConfigCard({
  name,
  config,
  onChange,
  state = 'default',
  disabled = false,
  placeholders,
  enabled,
  onEnabledChange,
  description,
  recommendation,
}: ModelConfigCardProps) {
  const isMasked = config.apiKey === API_KEY_MASKED
  const idPrefix = name.toLowerCase().replace(/\s+/g, '-')
  const hasCheckbox = enabled !== undefined
  // When the card supports a checkbox and is unchecked, force-disable inputs.
  const inputsDisabled = disabled || (hasCheckbox && !enabled)
  const dimmed = hasCheckbox && !enabled

  return (
    <Card
      className={cn(
        'flex flex-col gap-3 p-4',
        state === 'error' && 'border-destructive shadow-[0_0_0_3px_var(--card-error-ring)]'
      )}
    >
      <div className={cn('flex flex-col gap-1', dimmed && 'opacity-50')}>
        {/* Title row. When the card has a checkbox, wrap it in a <label> so
            clicking the title also toggles the checkbox. */}
        {hasCheckbox ? (
          <label
            htmlFor={`${idPrefix}-enabled`}
            className={cn(
              'flex items-center gap-2 self-start',
              disabled ? 'cursor-not-allowed' : 'cursor-pointer'
            )}
          >
            <Checkbox
              id={`${idPrefix}-enabled`}
              checked={enabled}
              onCheckedChange={(v) => onEnabledChange?.(v === true)}
              disabled={disabled}
              className="size-5"
              aria-label={`Enable ${name}`}
            />
            <h4 className="text-foreground text-base font-bold">{name}</h4>
          </label>
        ) : (
          <h4 className="text-foreground text-base font-bold">{name}</h4>
        )}
        {(description || recommendation) && (
          // Reserve a minimum height so adjacent cards line up at the form
          // fields below — sized for ~2 lines of description plus one line of
          // recommendation.
          <div className="flex min-h-[75px] flex-col gap-1">
            {description && (
              <p className="text-muted-foreground text-xs leading-relaxed">{description}</p>
            )}
            {recommendation && <div className="text-xs">{recommendation}</div>}
          </div>
        )}
      </div>

      <div className={cn('flex flex-col gap-2', dimmed && 'opacity-50')}>
        {FIELDS.map((field) => {
          const isApiKeyField = field.key === 'apiKey'
          const showMasked = isApiKeyField && isMasked
          const inputId = `${idPrefix}-${field.key}`

          return (
            <div key={field.key} className="flex flex-col gap-1">
              <label htmlFor={inputId} className="text-muted-foreground text-xs">
                {field.label}
              </label>
              <Input
                id={inputId}
                value={showMasked ? '••••••••' : config[field.key]}
                onChange={(e) => onChange({ [field.key]: e.target.value })}
                onFocus={showMasked ? () => onChange({ apiKey: '' }) : undefined}
                readOnly={showMasked}
                placeholder={placeholders?.[field.key] ?? DEFAULT_PLACEHOLDERS[field.key]}
                disabled={inputsDisabled}
                className={cn(
                  'bg-background h-8 text-sm shadow-none',
                  showMasked && 'cursor-pointer'
                )}
              />
            </div>
          )
        })}
      </div>
    </Card>
  )
}

/**
 * Shared alert for verification errors.
 * Renders each error line with the model name in bold.
 */
export function VerificationAlert({ errors }: { errors: string[] }) {
  if (errors.length === 0) return null

  return (
    <Alert variant="destructive">
      <TriangleAlert className="size-4" />
      <AlertTitle>Verification Failed</AlertTitle>
      <AlertDescription className="text-sm">
        {errors.map((err, i) => {
          const colonIdx = err.indexOf(': ')
          if (colonIdx === -1) return <div key={i}>{err}</div>
          return (
            <div key={i}>
              <span className="font-semibold">{err.slice(0, colonIdx)}</span>
              {err.slice(colonIdx)}
            </div>
          )
        })}
      </AlertDescription>
    </Alert>
  )
}

/**
 * Recommended-model row shown inside each ModelConfigCard's recommendation slot.
 * Wraps the model name in an external link.
 */
export function RecommendedModel({ name, url }: { name: string; url: string }) {
  return (
    <span className="text-muted-foreground">
      <span className="text-foreground font-bold">Recommended model:</span>{' '}
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary underline-offset-2 hover:underline"
      >
        {name}
      </a>
    </span>
  )
}
