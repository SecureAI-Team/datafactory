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

// Prompt variable type
export interface PromptVariable {
  name: string
  description?: string
  type?: string
  default?: unknown
  required?: boolean
}

// Prompt types
export interface PromptTemplate {
  id: number
  name: string
  type: string
  scenario_id?: string
  template: string
  variables: PromptVariable[]
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
  variables?: PromptVariable[]
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

// Parameter Definition types
export interface ParameterDefinition {
  id: number
  name: string
  code: string
  data_type: string
  unit?: string
  category?: string
  synonyms: string[]
  validation_rules?: Record<string, unknown>
  description?: string
  is_system: boolean
  created_at: string
  updated_at: string
}

export interface CreateParameterRequest {
  name: string
  code: string
  data_type: string
  unit?: string
  category?: string
  synonyms?: string[]
  validation_rules?: Record<string, unknown>
  description?: string
  is_system?: boolean
}

// Input parameter definition for calculation rules
export interface InputParam {
  name: string
  type: string
  required?: boolean
  default?: unknown
  description?: string
}

// Calculation Rule types
export interface CalculationRule {
  id: number
  name: string
  code: string
  description?: string
  formula: string
  input_schema?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  input_params: InputParam[] | string[]  // Can be either object array or string array
  output_type: string
  examples?: Array<{ input: Record<string, unknown>; output: unknown }>
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreateCalcRuleRequest {
  name: string
  code: string
  description?: string
  formula: string
  input_params?: string[]
  output_type?: string
  examples?: Array<{ input: Record<string, unknown>; output: unknown }>
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

  updateKUType: async (typeCode: string, data: Partial<CreateKUTypeRequest>): Promise<KUType> => {
    const response = await apiClient.put(`/api/config/ku-types/${typeCode}`, data)
    return response.data
  },

  deleteKUType: async (typeCode: string): Promise<void> => {
    await apiClient.delete(`/api/config/ku-types/${typeCode}`)
  },

  // Parameters
  getParameters: async (category?: string): Promise<{ parameters: ParameterDefinition[] }> => {
    const response = await apiClient.get('/api/config/parameters', { params: category ? { category } : {} })
    return response.data
  },

  createParameter: async (data: CreateParameterRequest): Promise<ParameterDefinition> => {
    const response = await apiClient.post('/api/config/parameters', data)
    return response.data.parameter
  },

  updateParameter: async (paramId: number, data: Partial<CreateParameterRequest>): Promise<ParameterDefinition> => {
    const response = await apiClient.put(`/api/config/parameters/${paramId}`, data)
    return response.data.parameter
  },

  deleteParameter: async (paramId: number): Promise<void> => {
    await apiClient.delete(`/api/config/parameters/${paramId}`)
  },

  // Calculation Rules
  getCalcRules: async (isActive?: boolean): Promise<{ rules: CalculationRule[] }> => {
    const response = await apiClient.get('/api/config/calc-rules', { params: isActive !== undefined ? { is_active: isActive } : {} })
    return response.data
  },

  createCalcRule: async (data: CreateCalcRuleRequest): Promise<CalculationRule> => {
    const response = await apiClient.post('/api/config/calc-rules', data)
    return response.data.rule
  },

  updateCalcRule: async (ruleId: number, data: Partial<CreateCalcRuleRequest>): Promise<CalculationRule> => {
    const response = await apiClient.put(`/api/config/calc-rules/${ruleId}`, data)
    return response.data.rule
  },

  deleteCalcRule: async (ruleId: number): Promise<void> => {
    await apiClient.delete(`/api/config/calc-rules/${ruleId}`)
  },

  testCalcRule: async (ruleId: number, inputs: Record<string, unknown>): Promise<{ success: boolean; result?: unknown; error?: string }> => {
    const response = await apiClient.post(`/api/config/calc-rules/${ruleId}/test`, { inputs })
    return response.data
  },

  // Interaction Flows
  getInteractionFlows: async (params?: { scenario_id?: string; is_active?: boolean }): Promise<{ flows: InteractionFlow[]; total: number }> => {
    const response = await apiClient.get('/api/config/interaction-flows', { params })
    return response.data
  },

  getInteractionFlow: async (flowId: string): Promise<InteractionFlow> => {
    const response = await apiClient.get(`/api/config/interaction-flows/${flowId}`)
    return response.data
  },

  createInteractionFlow: async (data: CreateInteractionFlowRequest): Promise<InteractionFlow> => {
    const response = await apiClient.post('/api/config/interaction-flows', data)
    return response.data
  },

  updateInteractionFlow: async (flowId: string, data: Partial<CreateInteractionFlowRequest>): Promise<InteractionFlow> => {
    const response = await apiClient.put(`/api/config/interaction-flows/${flowId}`, data)
    return response.data
  },

  deleteInteractionFlow: async (flowId: string): Promise<void> => {
    await apiClient.delete(`/api/config/interaction-flows/${flowId}`)
  },
}

// Interaction Flow types
export interface InteractionOption {
  id: string
  label: string
  icon?: string
  description?: string
  next?: string
}

export interface InteractionStep {
  id: string
  question: string
  type: 'single' | 'multiple' | 'input'
  options?: InteractionOption[]
  inputType?: 'text' | 'number' | 'date'
  placeholder?: string
  validation?: { min?: number; max?: number; pattern?: string }
  required?: boolean
  dependsOn?: { stepId: string; values: string[] }
}

export interface InteractionFlow {
  id: number
  flow_id: string
  name: string
  description?: string
  trigger_patterns: string[]
  scenario_id?: string
  steps: InteractionStep[]
  on_complete: 'calculate' | 'search' | 'generate'
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreateInteractionFlowRequest {
  flow_id: string
  name: string
  description?: string
  trigger_patterns?: string[]
  scenario_id?: string
  steps: InteractionStep[]
  on_complete?: string
  is_active?: boolean
}

export default configApi

