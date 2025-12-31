import { apiClient } from './client'

// Scenario types
export interface Scenario {
  id: number
  scenario_id: string
  name: string
  description?: string
  icon?: string
  intent_patterns: string[]
  retrieval_config: Record<string, unknown>
  response_template?: string
  quick_commands: string[]
  is_active: boolean
  sort_order: number
  created_at: string
}

export interface CreateScenarioRequest {
  scenario_id: string
  name: string
  description?: string
  icon?: string
  intent_patterns?: string[]
  retrieval_config?: Record<string, unknown>
  response_template?: string
  quick_commands?: string[]
  is_active?: boolean
  sort_order?: number
}

// Prompt types
export interface PromptTemplate {
  id: number
  name: string
  type: string
  scenario_id?: string
  template: string
  variables: string[]
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreatePromptRequest {
  name: string
  type: string
  scenario_id?: string
  template: string
  variables?: string[]
  is_active?: boolean
}

export interface PromptHistory {
  id: number
  prompt_id: number
  version: number
  template: string
  changed_by?: number
  change_reason?: string
  created_at: string
}

// KU Type types
export interface KUType {
  id: number
  type_code: string
  category: string
  display_name: string
  description?: string
  merge_strategy: string
  requires_expiry: boolean
  requires_approval: boolean
  visibility_default: string
  icon?: string
  sort_order: number
  is_active: boolean
}

export interface CreateKUTypeRequest {
  type_code: string
  category: string
  display_name: string
  description?: string
  merge_strategy?: string
  requires_expiry?: boolean
  requires_approval?: boolean
  visibility_default?: string
  icon?: string
  sort_order?: number
  is_active?: boolean
}

export const configApi = {
  // Scenarios
  getScenarios: async (): Promise<{ scenarios: Scenario[] }> => {
    const response = await apiClient.get('/api/config/scenarios')
    return response.data
  },

  createScenario: async (data: CreateScenarioRequest): Promise<Scenario> => {
    const response = await apiClient.post('/api/config/scenarios', data)
    return response.data
  },

  updateScenario: async (scenarioId: string, data: Partial<CreateScenarioRequest>): Promise<Scenario> => {
    const response = await apiClient.put(`/api/config/scenarios/${scenarioId}`, data)
    return response.data
  },

  deleteScenario: async (scenarioId: string): Promise<void> => {
    await apiClient.delete(`/api/config/scenarios/${scenarioId}`)
  },

  // Prompts
  getPrompts: async (params?: { type?: string; scenario_id?: string }): Promise<{ prompts: PromptTemplate[] }> => {
    const response = await apiClient.get('/api/config/prompts', { params })
    return response.data
  },

  createPrompt: async (data: CreatePromptRequest): Promise<PromptTemplate> => {
    const response = await apiClient.post('/api/config/prompts', data)
    return response.data
  },

  updatePrompt: async (promptId: number, data: Partial<CreatePromptRequest>): Promise<PromptTemplate> => {
    const response = await apiClient.put(`/api/config/prompts/${promptId}`, data)
    return response.data
  },

  getPromptHistory: async (promptId: number): Promise<{ history: PromptHistory[] }> => {
    const response = await apiClient.get(`/api/config/prompts/${promptId}/history`)
    return response.data
  },

  revertPrompt: async (promptId: number, version: number): Promise<PromptTemplate> => {
    const response = await apiClient.post(`/api/config/prompts/${promptId}/revert`, { version })
    return response.data
  },

  // KU Types
  getKUTypes: async (): Promise<{ ku_types: KUType[] }> => {
    const response = await apiClient.get('/api/config/ku-types')
    return response.data
  },

  createKUType: async (data: CreateKUTypeRequest): Promise<KUType> => {
    const response = await apiClient.post('/api/config/ku-types', data)
    return response.data
  },

  updateKUType: async (typeId: number, data: Partial<CreateKUTypeRequest>): Promise<KUType> => {
    const response = await apiClient.put(`/api/config/ku-types/${typeId}`, data)
    return response.data
  },
}

export default configApi

