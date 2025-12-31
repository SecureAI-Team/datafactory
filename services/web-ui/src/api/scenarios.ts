import { apiClient } from './client'

export interface Scenario {
  id: number
  scenario_id: string
  name: string
  description?: string
  icon?: string
  intent_patterns: unknown[]
  retrieval_config: Record<string, unknown>
  response_template?: string
  quick_commands: QuickCommand[]
  is_active: boolean
  sort_order: number
}

export interface QuickCommand {
  command: string
  label: string
  description?: string
  icon?: string
}

export const scenariosApi = {
  /**
   * Get all active scenarios
   */
  getScenarios: async (): Promise<{ scenarios: Scenario[] }> => {
    const response = await apiClient.get('/api/config/scenarios', {
      params: { active_only: true }
    })
    return response.data
  },

  /**
   * Get scenario by ID
   */
  getScenario: async (scenarioId: string): Promise<Scenario> => {
    const response = await apiClient.get(`/api/config/scenarios/${scenarioId}`)
    return response.data
  },
}

export default scenariosApi

