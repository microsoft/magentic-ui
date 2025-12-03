/** Client for the `/api/settings/agents` endpoints. */
import { useQuery, useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

export interface OrchestratorAgentSettings {
  max_rounds: number
}

export interface WebSurferAgentSettings {
  max_rounds: number
}

export interface AgentSettings {
  orchestrator: OrchestratorAgentSettings
  web_surfer: WebSurferAgentSettings
}

export function getAgentSettings(): Promise<AgentSettings> {
  return apiClient.get<AgentSettings>('/settings/agents')
}

export function updateAgentSettings(payload: AgentSettings): Promise<AgentSettings> {
  return apiClient.put<AgentSettings>('/settings/agents', payload)
}

const agentSettingsKeys = {
  all: ['settings', 'agents'] as const,
}

export function useAgentSettings() {
  return useQuery({
    queryKey: agentSettingsKeys.all,
    queryFn: getAgentSettings,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
}

export function useUpdateAgentSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateAgentSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(agentSettingsKeys.all, data)
    },
  })
}

export function invalidateAgentSettings(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: agentSettingsKeys.all })
}
