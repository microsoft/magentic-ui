/**
 * Message Module
 *
 * Centralized message parsing and utilities.
 * All message-related logic should be imported from this module.
 */

// New parsed message types
export type {
  ParsedMessage,
  ParsedUserMessage,
  ParsedCuaBrowserMessage,
  ParsedCuaNonBrowserMessage,
  ParsedScreenshotMessage,
  ParsedCodeExecutionMessage,
  ParsedOrchestratorToolMessage,
  ParsedToolResultMessage,
  ParsedFinalAnswerMessage,
  ParsedSummaryMessage,
  ParsedBrowserAddressMessage,
  ParsedInternalMessage,
  ParsedErrorMessage,
  ParsedSystemStatusMessage,
  ParsedInputRequestMessage,
  ParsedTextMessage,
  BrowserToolArgs,
  NonBrowserToolArgs,
} from '@/types/message'

// Constants
export {
  BROWSER_TOOLS,
  NON_BROWSER_TOOLS,
  TOOL_LABELS,
  ORCHESTRATOR_TOOL_LABELS,
  CUA_AGENT_SOURCE,
  ORCHESTRATOR_AGENT_SOURCE,
  AGENT_MODE,
  isBrowserTool,
  isNonBrowserTool,
  shouldDemoteCuaFinalAnswer,
  toAgentMode,
  getCuaToolLabel,
  getOrchestratorToolLabel,
  type BrowserTool,
  type NonBrowserTool,
  type AgentMode,
} from './constants'

// Parser (utils are internal to parser, not re-exported)
export { parseMessage, parseMessages } from './parser'
