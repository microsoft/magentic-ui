import type { ReactNode } from 'react'
import { Card } from '@/components/ui/card'
import { SAMPLE_TASKS } from '@/lib/sampleTasks'
import type { SampleTask } from '@/lib/sampleTasks'

interface SampleTaskCardsProps {
  /** Title shown above the task cards. Pass `null` to hide. */
  title?: ReactNode
  /** Called when user clicks a task card's CTA button */
  onTaskSelect: (task: SampleTask) => void
}

/**
 * Displays sample task cards. Used in SampleTasksPage
 * and the new-session empty state.
 */
export function SampleTaskCards({
  title = 'Try a sample task:',
  onTaskSelect,
}: SampleTaskCardsProps) {
  return (
    <div className="flex flex-col gap-4">
      {title !== null && <span className="text-foreground text-sm font-bold">{title}</span>}
      {SAMPLE_TASKS.map((task) => (
        <Card
          key={task.id}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onTaskSelect(task)
            }
          }}
          className="hover:bg-card-hover focus-visible:ring-ring flex cursor-pointer items-center gap-3 p-4 transition-colors focus-visible:ring-2 focus-visible:outline-none"
          onClick={() => onTaskSelect(task)}
          aria-label={`${task.label}`}
        >
          <task.icon className="text-primary size-5 shrink-0" />
          <span className="text-foreground flex-1 text-[13px] leading-snug">{task.label}</span>
        </Card>
      ))}
    </div>
  )
}
