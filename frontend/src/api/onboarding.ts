/**
 * Onboarding API
 *
 * Client functions for the /api/onboarding endpoints.
 */
import { useQuery, type QueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

// =============================================================================
// Constants
// =============================================================================

/**
 * Sentinel value the backend returns instead of real API keys.
 * When sent back to the backend, it means "keep the existing DB value".
 */
export const API_KEY_MASKED = '__MASKED__'

/**
 * Deployment mode controlling which agents are active.
 * Mirrors `AgentMode` in `magentic_ui_config.py`.
 */
export type AgentMode = 'all' | 'omniagent_only' | 'websurfer_only'

// =============================================================================
// Types (mirror backend Pydantic models)
// =============================================================================

export interface ModelInfoConfig {
  vision: boolean
  function_calling: boolean
  json_output: boolean
  family: string
  structured_output: boolean
  multiple_system_messages: boolean
}

export interface ModelClientConfig {
  provider: string
  config: {
    model: string
    api_key: string
    base_url: string
    max_retries: number
    model_info: ModelInfoConfig
  }
}

export interface OnboardingStatus {
  onboarding_completed: boolean
}

export interface ModelEndpointsResponse {
  orchestrator: ModelClientConfig | null
  web_surfer: ModelClientConfig | null
  agent_mode: AgentMode
}

export interface ModelEndpointVerification {
  success: boolean
  error?: string
}

export interface ModelVerifyResponse {
  /** Present when the verify request included `orchestrator`. */
  orchestrator?: ModelEndpointVerification
  /** Present when the verify request included `web_surfer`. */
  web_surfer?: ModelEndpointVerification
}

export interface ModelEndpointInput {
  base_url: string
  model: string
  api_key: string
}

export interface VerifyEndpointsPayload {
  /** Required when `agent_mode` includes the orchestrator. */
  orchestrator?: ModelEndpointInput
  /** Required when `agent_mode` includes the web surfer. */
  web_surfer?: ModelEndpointInput
  /** Defaults to 'all' on the backend. */
  agent_mode?: AgentMode
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Check if onboarding is completed.
 * Lightweight — reads only the Settings.onboarding_completed column.
 */
export function getOnboardingStatus(): Promise<OnboardingStatus> {
  return apiClient.get<OnboardingStatus>('/onboarding/status')
}

/**
 * Get saved model endpoints (masked api_keys).
 * Used by settings page.
 */
export function getOnboardingEndpoints(): Promise<ModelEndpointsResponse> {
  return apiClient.get<ModelEndpointsResponse>('/onboarding/endpoints')
}

/**
 * Verify model endpoints and save them to DB.
 * Only sends user-provided fields; backend fills role defaults.
 *
 * Caller must include the role(s) required by `agent_mode`. The inactive
 * role may be omitted; its previously saved config is left untouched.
 */
export function verifyEndpoints(payload: VerifyEndpointsPayload): Promise<ModelVerifyResponse> {
  return apiClient.post<ModelVerifyResponse>('/onboarding/verify', payload)
}

/**
 * Update only the active `agent_mode` — no model verification.
 *
 * The backend rejects with HTTP 400 if the new mode requires a model that
 * has no saved config yet.
 */
export function setAgentMode(mode: AgentMode): Promise<{ agent_mode: AgentMode }> {
  return apiClient.post<{ agent_mode: AgentMode }>('/onboarding/agent-mode', {
    agent_mode: mode,
  })
}

/**
 * Mark onboarding as completed.
 * Requires both endpoints to be verified.
 */
export function completeOnboarding(): Promise<void> {
  return apiClient.post('/onboarding/complete')
}

/**
 * Reset onboarding config (clear model endpoints and completed flag).
 */
export function resetOnboarding(): Promise<void> {
  return apiClient.post('/onboarding/reset')
}

// =============================================================================
// Query Hooks
// =============================================================================

const onboardingKeys = {
  all: ['onboarding'] as const,
  endpoints: () => [...onboardingKeys.all, 'endpoints'] as const,
}

/**
 * The user's currently-saved `agent_mode` from settings.
 *
 * Cached indefinitely (`gcTime: Infinity` so the data survives even with no
 * observers). Invalidate via `invalidateOnboardingEndpoints` after mutations.
 */
export function useCurrentAgentMode(): { agentMode: AgentMode | null; isLoading: boolean } {
  const query = useQuery({
    queryKey: onboardingKeys.endpoints(),
    queryFn: getOnboardingEndpoints,
    staleTime: Infinity,
    gcTime: Infinity,
    refetchOnWindowFocus: false,
    select: (data) => data.agent_mode ?? null,
  })
  return { agentMode: query.data ?? null, isLoading: query.isLoading }
}

/** Invalidate the cached onboarding endpoints (and therefore `agent_mode`). */
export function invalidateOnboardingEndpoints(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: onboardingKeys.endpoints() })
}
