/**
 * CUA (Computer Use Agent) Message Component
 *
 * Displays a group of web browser actions in a collapsible section.
 * Used for: Visiting URLs, Scrolling, Typing, Clicking, etc.
 *
 * Tense handling:
 * - Progressive tense (Visiting, Typing): only the LAST action in the LAST group when sessionStatus === 'active'
 * - Past tense (Visited, Typed): all other actions
 * - Header: progressive if any action uses progressive tense
 */

import { useState } from 'react'
import { Globe } from 'lucide-react'
import { CollapsibleHeader } from './CollapsibleHeader'
import { useCollapsibleGroup } from '@/hooks'
import { type SessionStatus } from '@/types'
import { getCuaToolLabel } from '@/lib/messages'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/stores/uiStore'

// =============================================================================
// Types
// =============================================================================

/** Tool arguments from metadata.tool_args */
export interface ToolArgs {
  action?: string
  url?: string
  query?: string
  text?: string
  coordinate?: [number, number]
  pixels?: number
  keys?: string[]
  time?: number
  press_enter?: boolean
  delete_existing_text?: boolean
  thoughts?: string
  /** pause_and_memorize_fact: the memorized fact text */
  fact?: string
  /** read_page_answer_question / ask_user_question */
  question?: string
  /** run_command */
  command?: string
  [key: string]: unknown
}

export interface CuaAction {
  /** Source message ID (for Chat ↔ Browser linkage) */
  messageId: string
  /** Raw action text (fallback display) */
  rawContent: string
  /** Tool name from metadata.tool (e.g., 'visit_url', 'type', 'click') */
  tool?: string
  /** Structured arguments from metadata.tool_args */
  toolArgs?: ToolArgs
  /** Whether this action has completed (a follow-up message arrived after the tool call).
   *  Controls tense: incomplete → progressive ("Visiting"), complete → past ("Visited"). */
  isComplete?: boolean
  /** Screenshot URL captured after this action completed (for progress bar/carousel) */
  screenshotUrl?: string
  /** Description of the completed action (past tense) from screenshot message. */
  actionResult?: string
  /** Error message text — when set, this row renders as an inline error within the group */
  errorContent?: string
}

interface CuaMessageProps {
  actions: CuaAction[]
  /** Unique ID for this CUA group (for expand state tracking) */
  groupId: string
  /** Session ID (for expand state tracking) */
  sessionId: number
  /** Whether progressive tense can be used (true if no messages after this group) */
  canUseProgressiveTense?: boolean
  /** Current session status - used to determine tense */
  sessionStatus?: SessionStatus
  /** Whether a live noVNC stream is available — when true, the latest-thoughts
      subtitle is hidden (the user can already see the action in the live browser). */
  hasLiveBrowser?: boolean
  /** Called when an action item is clicked (for Browser screenshot sync) */
  onActionClick?: (action: CuaAction) => void
  /** ID of the currently highlighted action (from Browser playback) */
  highlightedActionId?: string | null
}

// =============================================================================
// Constants & Helpers
// =============================================================================

// Header labels: [progressive, past]
const HEADER_LABELS: [string, string] = ['Using web browser', 'Used web browser']

/**
 * Extract detail string from tool args for display.
 * Returns simplified URL, search query, typed text, scroll direction, keys, or coordinates.
 *
 * Note: Some parsed fields are not displayed (kept for potential future use):
 * - action: redundant with metadata.tool
 * - press_enter, delete_existing_text: type action modifiers
 * - thoughts: stored in rawContent, used as fallback display
 */
function getToolDetail(tool: string | undefined, toolArgs: ToolArgs | undefined): string | null {
  if (!tool || !toolArgs) return null

  const toolLower = tool.toLowerCase()

  switch (toolLower) {
    case 'visit_url':
      if (toolArgs.url) {
        try {
          const { hostname } = new URL(toolArgs.url)
          const display = hostname.replace(/^www\./, '')
          return display.length > 40 ? display.slice(0, 40) + '...' : display
        } catch {
          // Invalid URL - fallback to truncation
          return toolArgs.url.length > 40 ? toolArgs.url.slice(0, 40) + '...' : toolArgs.url
        }
      }
      break
    case 'web_search':
      if (toolArgs.query) {
        const query = toolArgs.query
        return query.length > 40 ? query.slice(0, 40) + '...' : query
      }
      break
    case 'type':
    case 'input_text':
      if (toolArgs.text) {
        const text = toolArgs.text
        return text.length > 40 ? text.slice(0, 40) + '...' : text
      }
      break
    case 'click':
    case 'left_click':
    case 'double_click':
    case 'right_click':
    case 'triple_click':
      if (toolArgs.coordinate) {
        const [x, y] = toolArgs.coordinate
        return `(${x}, ${y})`
      }
      break
    case 'left_click_drag':
      if (toolArgs.coordinate) {
        const [x, y] = toolArgs.coordinate
        return `to (${x}, ${y})`
      }
      break
    case 'scroll':
      // Negative pixels = scroll down, positive = scroll up
      if (toolArgs.pixels !== undefined) {
        return toolArgs.pixels < 0 ? 'down' : 'up'
      }
      break
    case 'hscroll':
      // Negative pixels = scroll left, positive = scroll right
      if (toolArgs.pixels !== undefined) {
        return toolArgs.pixels < 0 ? 'left' : 'right'
      }
      break
    case 'key':
    case 'keypress':
      // Keys are pressed together as a combination, not in sequence
      if (toolArgs.keys && Array.isArray(toolArgs.keys)) {
        const keysStr = toolArgs.keys.join('+')
        return keysStr.length > 40 ? keysStr.slice(0, 40) + '...' : keysStr
      }
      break
    case 'mouse_move':
    case 'hover':
      if (toolArgs.coordinate) {
        const [x, y] = toolArgs.coordinate
        return `to (${x}, ${y})`
      }
      break
    case 'history_back':
      return null
    case 'wait':
    case 'sleep':
      if (toolArgs.time !== undefined) {
        return `${toolArgs.time}s`
      }
      break
    case 'pause_and_memorize_fact':
      if (toolArgs.fact) {
        return toolArgs.fact
      }
      break
    case 'read_page_answer_question':
      if (toolArgs.question) {
        const q = toolArgs.question
        return q.length > 60 ? q.slice(0, 60) + '...' : q
      }
      break
    case 'run_command':
      if (toolArgs.command) {
        const c = toolArgs.command
        return c.length > 60 ? c.slice(0, 60) + '...' : c
      }
      break
  }

  return null
}

// =============================================================================
// Component
// =============================================================================

export function CuaMessage({
  actions,
  groupId,
  sessionId,
  canUseProgressiveTense = false,
  sessionStatus,
  hasLiveBrowser = false,
  onActionClick,
  highlightedActionId,
}: CuaMessageProps) {
  // Collapsible state management
  const { isExpanded, toggle } = useCollapsibleGroup(sessionId, groupId, 'toolCall')
  const showBrowserActionDetails = useUIStore((s) => s.showBrowserActionDetails)

  // Use progressive tense only when allowed AND session is active
  const useProgressiveTense = canUseProgressiveTense && sessionStatus === 'active'

  // Header label: progressive if using progressive tense
  const headerLabel = useProgressiveTense ? HEADER_LABELS[0] : HEADER_LABELS[1]

  // Latest action's reasoning (thoughts) — surfaced under the header so users
  // see what the agent is doing without expanding the group.
  // Hidden when: live browser is active, group is expanded (thoughts shown inline),
  // or there are newer messages after this group (thoughts are stale).
  const latestThoughts = actions[actions.length - 1]?.toolArgs?.thoughts?.trim() || null
  const showLatestThoughts =
    latestThoughts && !hasLiveBrowser && !isExpanded && canUseProgressiveTense

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-1">
        <CollapsibleHeader
          icon={<Globe className="size-4" />}
          label={headerLabel}
          isExpanded={isExpanded}
          onToggle={toggle}
          isActive={useProgressiveTense}
        />
        {showLatestThoughts && (
          <div className="text-muted-foreground ml-6 text-sm">{latestThoughts}</div>
        )}
      </div>

      {isExpanded && (
        // Vertical line + indented content layout
        <div className="border-border ml-2 flex flex-col gap-0.5 border-l pl-2">
          {actions.map((action, index) => {
            const isHighlighted = highlightedActionId === action.messageId

            if (action.errorContent) {
              return (
                <CuaErrorRow
                  key={`${action.messageId}-${showBrowserActionDetails}`}
                  errorContent={action.errorContent}
                  failedTool={action.tool}
                  failedToolArgs={action.toolArgs}
                  defaultExpanded={showBrowserActionDetails}
                  isHighlighted={isHighlighted}
                />
              )
            }

            // Use progressive tense if:
            // 1. This action has no screenshot yet (action still in progress)
            // 2. AND session is active
            // 3. AND this is the last action AND canUseProgressiveTense is true
            const isLastAction = index === actions.length - 1
            const actionInProgress = !action.isComplete
            const actionUseProgressiveTense =
              actionInProgress && useProgressiveTense && isLastAction

            const label = getCuaToolLabel(action.tool, actionUseProgressiveTense)
            const detail = getToolDetail(action.tool, action.toolArgs)
            const thoughts = action.toolArgs?.thoughts?.trim() || null

            // Only clickable if action has a screenshot URL (can be shown in browser playback)
            const isClickable = action.screenshotUrl && onActionClick

            return (
              <div
                key={action.messageId}
                className={cn(isClickable && 'cursor-pointer')}
                onClick={isClickable ? () => onActionClick(action) : undefined}
              >
                <div
                  className={cn(
                    'text-foreground w-fit rounded-md px-2 text-sm break-words',
                    isHighlighted && 'bg-accent'
                  )}
                >
                  <span className="font-bold">{label}</span>
                  {detail && <span className="ml-1.5">{detail}</span>}
                </div>
                {(showBrowserActionDetails ||
                  (isLastAction && actionInProgress && !hasLiveBrowser)) &&
                  thoughts && (
                    <div className="text-muted-foreground px-2 pb-1 text-xs break-words whitespace-pre-line">
                      {thoughts}
                    </div>
                  )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// CuaErrorRow
// =============================================================================

interface CuaErrorRowProps {
  errorContent: string
  failedTool: string | undefined
  failedToolArgs: ToolArgs | undefined
  defaultExpanded: boolean
  isHighlighted: boolean
}

/**
 * Error row inside a CUA group. Shows which action failed (action
 * label + detail). Click toggles the full error text below.
 * Defaults to expanded/collapsed based on the `showBrowserActionDetails` toggle;
 * click overrides for this individual row.
 */
function CuaErrorRow({
  errorContent,
  failedTool,
  failedToolArgs,
  defaultExpanded,
  isHighlighted,
}: CuaErrorRowProps) {
  const [override, setOverride] = useState<boolean | null>(null)
  const isExpanded = override ?? defaultExpanded

  const failedLabel = failedTool ? getCuaToolLabel(failedTool, true) : null
  const failedDetail = getToolDetail(failedTool, failedToolArgs)

  return (
    <div className="cursor-pointer" onClick={() => setOverride(!isExpanded)}>
      <div
        className={cn(
          'text-status-error w-fit rounded-md px-2 text-sm break-words',
          isHighlighted && 'bg-accent'
        )}
      >
        <span className="font-bold">Error</span>
        {(failedLabel || failedDetail) && (
          <span className="ml-1.5">
            {failedLabel}
            {failedDetail && ` ${failedDetail}`}
          </span>
        )}
      </div>
      {isExpanded && (
        <div className="text-status-error px-2 pb-1 text-xs break-words whitespace-pre-line">
          {errorContent}
        </div>
      )}
    </div>
  )
}
