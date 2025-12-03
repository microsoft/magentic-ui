/**
 * Message Constants
 *
 * Tool classifications for message parsing and display.
 */

import { Globe, FileText, Terminal, Search, ArrowDownUp, Wrench } from 'lucide-react'

// =============================================================================
// Agent Source Names
// =============================================================================

export const CUA_AGENT_SOURCE = 'web_surfer'
export const ORCHESTRATOR_AGENT_SOURCE = 'OmniAgent'

// =============================================================================
// Agent Mode (mirrors backend `magentic_ui.AgentMode` enum)
// =============================================================================
//
// The string value persisted on `Run.agent_mode` by the backend at the
// moment the run starts. Used by the parser to decide whether the
// web_surfer's `final_answer` is the real final answer (FARA-only mode)
// or an intermediate hand-off (OmniAgent modes).
export const AGENT_MODE = {
  ALL: 'all',
  OMNIAGENT_ONLY: 'omniagent_only',
  WEBSURFER_ONLY: 'websurfer_only',
} as const

export type AgentMode = (typeof AGENT_MODE)[keyof typeof AGENT_MODE]

const KNOWN_AGENT_MODES = new Set<string>(Object.values(AGENT_MODE))

/**
 * Narrow a raw string from the backend (`Run.agent_mode`) to the typed
 * ``AgentMode`` enum. Returns ``null`` for unknown / missing values so
 * the rest of the frontend can rely on ``AgentMode | null`` everywhere.
 *
 * Backend may add new modes that this version of the frontend doesn't
 * recognize — we treat those the same as legacy null runs (unknown), which
 * matches the information-preservation policy in ``shouldDemoteCuaFinalAnswer``.
 */
export function toAgentMode(value: string | null | undefined): AgentMode | null {
  if (value && KNOWN_AGENT_MODES.has(value)) {
    return value as AgentMode
  }
  return null
}

/** Modes in which OmniAgent owns the real final answer (CUA's is intermediate). */
const ORCHESTRATOR_OWNS_FINAL_ANSWER = new Set<AgentMode>([
  AGENT_MODE.ALL,
  AGENT_MODE.OMNIAGENT_ONLY,
])

/**
 * Should the web_surfer's `final_answer` be demoted to an internal message
 * (because OmniAgent owns the real final answer in this run)?
 *
 * - `omniagent_only` / `all`: yes — demote.
 * - `websurfer_only`: no — CUA produced the real answer.
 * - null (legacy run, or unknown mode from a newer backend): no —
 *   keep it as final-answer to avoid hiding the only real answer in
 *   legacy FARA-only sessions. The trade-off is that legacy OmniAgent
 *   sessions show one extra intermediate final-answer card.
 */
export function shouldDemoteCuaFinalAnswer(agentMode: AgentMode | null | undefined): boolean {
  if (!agentMode) return false
  return ORCHESTRATOR_OWNS_FINAL_ANSWER.has(agentMode)
}

// =============================================================================
// Browser Tools — GUI actions that produce a screenshot
// =============================================================================

/** GUI actions producing a follow-up screenshot (clicks, scrolls, nav, etc.). */
export const BROWSER_TOOLS = [
  'visit_url',
  'web_search',
  'type',
  'input_text',
  'left_click',
  'click',
  'double_click',
  'right_click',
  'triple_click',
  'left_click_drag',
  'scroll',
  'hscroll',
  'key',
  'keypress',
  'mouse_move',
  'hover',
  'history_back',
  'wait',
  'sleep',
] as const

export type BrowserTool = (typeof BROWSER_TOOLS)[number]

/**
 * Check if a tool is a browser tool
 */
export function isBrowserTool(tool: string): tool is BrowserTool {
  return BROWSER_TOOLS.includes(tool as BrowserTool)
}

// =============================================================================
// Non-Browser Tools — Non-GUI / text-output tools
// =============================================================================

/**
 * Tools that don't drive the browser GUI directly. The backend still emits a
 * screenshot after each one, but the UI shows these as inline action rows
 * rather than click/scroll details. terminate/stop flush the CUA group; the
 * rest remain within the group like other action rows.
 */
export const NON_BROWSER_TOOLS = [
  'pause_and_memorize_fact',
  'read_page_answer_question',
  'run_command',
  'terminate',
  'stop',
] as const

export type NonBrowserTool = (typeof NON_BROWSER_TOOLS)[number]

export function isNonBrowserTool(tool: string): tool is NonBrowserTool {
  return NON_BROWSER_TOOLS.includes(tool as NonBrowserTool)
}

// =============================================================================
// Tool Display Labels
// =============================================================================

/**
 * Tool name to display labels: [progressive, past]
 * Used for CUA message tense handling.
 */
export const TOOL_LABELS: Record<string, [string, string]> = {
  // Browser tools
  visit_url: ['Visiting', 'Visited'],
  web_search: ['Searching', 'Searched'],
  type: ['Typing', 'Typed'],
  input_text: ['Typing', 'Typed'],
  left_click: ['Clicking', 'Clicked'],
  click: ['Clicking', 'Clicked'],
  double_click: ['Double-clicking', 'Double-clicked'],
  right_click: ['Right-clicking', 'Right-clicked'],
  triple_click: ['Triple-clicking', 'Triple-clicked'],
  left_click_drag: ['Dragging', 'Dragged'],
  scroll: ['Scrolling', 'Scrolled'],
  hscroll: ['Scrolling', 'Scrolled'],
  key: ['Pressing', 'Pressed'],
  keypress: ['Pressing', 'Pressed'],
  mouse_move: ['Moving cursor', 'Moved cursor'],
  hover: ['Moving cursor', 'Moved cursor'],
  history_back: ['Going back', 'Went back'],
  wait: ['Waiting', 'Waited'],
  sleep: ['Waiting', 'Waited'],
  // Non-browser tools
  pause_and_memorize_fact: ['Remembering', 'Remembered'],
  read_page_answer_question: ['Reading page', 'Read page'],
  run_command: ['Running command', 'Ran command'],
  terminate: ['Finishing', 'Finished'],
  stop: ['Finishing', 'Finished'],
}

/**
 * Get display label for a CUA tool
 */
export function getCuaToolLabel(tool: string | undefined, useProgressiveTense: boolean): string {
  if (!tool) return 'Browser action'
  const labels = TOOL_LABELS[tool.toLowerCase()]
  if (!labels) return 'Browser action'
  return useProgressiveTense ? labels[0] : labels[1]
}

// =============================================================================
// Orchestrator Tools - OmniAgent tool_call labels & icons
// =============================================================================

/**
 * Display labels for orchestrator tools: [progressive, past]
 * Used for OmniAgent tool_call and tool_result messages.
 *
 * Based on OmniAgent tool definitions. When backend adds new tools,
 * the fallback in getOrchestratorToolLabel() formats the tool name automatically.
 */
export const ORCHESTRATOR_TOOL_LABELS: Record<string, [string, string]> = {
  // Shell
  bash: ['Running Bash command', 'Ran Bash command'],
  // File operations
  create: ['Creating file', 'Created file'],
  open: ['Opening file', 'Opened file'],
  edit: ['Editing file', 'Edited file'],
  insert: ['Inserting content', 'Inserted content'],
  // File navigation
  goto: ['Navigating to line', 'Navigated to line'],
  scroll_down: ['Scrolling down', 'Scrolled down'],
  scroll_up: ['Scrolling up', 'Scrolled up'],
  // Search
  search_dir: ['Searching in directory', 'Searched in directory'],
  search_file: ['Searching in file', 'Searched in file'],
  find_file: ['Looking for file', 'Looked for file'],
  // Browser delegation
  delegate_cua: ['Using web browser', 'Finished web browsing'],
}

/**
 * Icon category for orchestrator tools.
 * Lucide icon names grouped by tool function.
 */
type OrchestratorToolIconCategory =
  | 'terminal'
  | 'file'
  | 'navigation'
  | 'search'
  | 'globe'
  | 'wrench'

/** Map tool names to icon categories */
const ORCHESTRATOR_TOOL_ICON_CATEGORIES: Record<string, OrchestratorToolIconCategory> = {
  bash: 'terminal',
  create: 'file',
  open: 'file',
  edit: 'file',
  insert: 'file',
  goto: 'navigation',
  scroll_down: 'navigation',
  scroll_up: 'navigation',
  search_dir: 'search',
  search_file: 'search',
  find_file: 'search',
  delegate_cua: 'globe',
}

/**
 * Get icon category for an orchestrator tool.
 * Components use this to render the appropriate Lucide icon.
 */
function getOrchestratorToolIconCategory(tool: string | undefined): OrchestratorToolIconCategory {
  if (!tool) return 'wrench'
  return ORCHESTRATOR_TOOL_ICON_CATEGORIES[tool] ?? 'wrench'
}

// =============================================================================
// Orchestrator Tool Icons (JSX)
// =============================================================================

const ICON_CLASS = 'size-4 shrink-0'

const CATEGORY_ICONS: Record<OrchestratorToolIconCategory, React.ReactNode> = {
  terminal: <Terminal className={ICON_CLASS} />,
  file: <FileText className={ICON_CLASS} />,
  navigation: <ArrowDownUp className={ICON_CLASS} />,
  search: <Search className={ICON_CLASS} />,
  globe: <Globe className={ICON_CLASS} />,
  wrench: <Wrench className={ICON_CLASS} />,
}

/**
 * Get the Lucide icon element for an orchestrator tool.
 */
export function getOrchestratorToolIcon(tool: string | undefined): React.ReactNode {
  const category = getOrchestratorToolIconCategory(tool)
  return CATEGORY_ICONS[category]
}

/**
 * Format a tool name for display: replace underscores with spaces.
 */
function formatToolName(tool: string): string {
  return tool.replace(/_/g, ' ')
}

/**
 * Get display label for an orchestrator tool
 */
export function getOrchestratorToolLabel(
  tool: string | undefined,
  useProgressiveTense: boolean
): string {
  if (!tool) return 'Running tool'
  const labels = ORCHESTRATOR_TOOL_LABELS[tool]
  if (!labels) {
    const name = formatToolName(tool)
    return useProgressiveTense ? `Running ${name}` : `Ran ${name}`
  }
  return useProgressiveTense ? labels[0] : labels[1]
}
