/**
 * API Module Exports
 */
export { apiClient, ApiError } from './client'
export type { ApiResponse } from './client'

export {
  getOnboardingStatus,
  getOnboardingEndpoints,
  verifyEndpoints,
  setAgentMode,
  completeOnboarding,
  resetOnboarding,
  useCurrentAgentMode,
  invalidateOnboardingEndpoints,
} from './onboarding'
export type {
  AgentMode,
  OnboardingStatus,
  ModelEndpointsResponse,
  ModelClientConfig,
  ModelInfoConfig,
  ModelVerifyResponse,
  ModelEndpointVerification,
  ModelEndpointInput,
  VerifyEndpointsPayload,
} from './onboarding'

export {
  getAgentSettings,
  updateAgentSettings,
  useAgentSettings,
  useUpdateAgentSettings,
  invalidateAgentSettings,
} from './agentSettings'
export type {
  AgentSettings,
  OrchestratorAgentSettings,
  WebSurferAgentSettings,
} from './agentSettings'

export {
  sessionKeys,
  useSessionList,
  useSessionsWithStatus,
  useUpdateSession,
  useDeleteSession,
} from './sessions'
