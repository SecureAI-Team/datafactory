import { apiClient } from './client'

// LLM Provider types
export interface LLMProvider {
  id: number
  provider_code: string
  provider_name: string
  api_base_url?: string
  has_api_key: boolean
  is_active: boolean
  is_default: boolean
  config: Record<string, unknown>
  created_at: string
}

export interface CreateProviderRequest {
  provider_code: string
  provider_name: string
  api_base_url?: string
  api_key?: string
  is_active?: boolean
  is_default?: boolean
  config?: Record<string, unknown>
}

// LLM Model types
export interface LLMModel {
  id: number
  provider_id: number
  provider_code?: string
  provider_name?: string
  model_code: string
  model_name: string
  model_type: string
  capabilities: string[]
  context_window?: number
  max_output_tokens?: number
  cost_per_1k_input?: number
  cost_per_1k_output?: number
  is_active: boolean
  is_default: boolean
  config: Record<string, unknown>
}

export interface CreateModelRequest {
  provider_id: number
  model_code: string
  model_name: string
  model_type: string
  capabilities?: string[]
  context_window?: number
  max_output_tokens?: number
  cost_per_1k_input?: number
  cost_per_1k_output?: number
  is_active?: boolean
  is_default?: boolean
  config?: Record<string, unknown>
}

// LLM Assignment types
export interface LLMAssignment {
  id: number
  use_case: string
  model_id: number
  model_code?: string
  model_name?: string
  fallback_model_id?: number
  fallback_model_code?: string
  fallback_model_name?: string
  priority: number
  config_override: Record<string, unknown>
  is_active: boolean
}

export interface UpdateAssignmentRequest {
  model_id: number
  fallback_model_id?: number
  config_override?: Record<string, unknown>
}

// Test types
export interface LLMTestRequest {
  model_code: string
  prompt: string
  max_tokens?: number
}

export interface LLMTestResponse {
  model_code: string
  prompt: string
  status: string
  response: string
  tokens_used: number
  latency_ms: number
}

export const llmApi = {
  // Providers
  getProviders: async (activeOnly = false): Promise<{ providers: LLMProvider[] }> => {
    const response = await apiClient.get('/api/config/llm/providers', {
      params: { active_only: activeOnly }
    })
    return response.data
  },

  getProvider: async (providerId: number): Promise<LLMProvider> => {
    const response = await apiClient.get(`/api/config/llm/providers/${providerId}`)
    return response.data
  },

  createProvider: async (data: CreateProviderRequest): Promise<LLMProvider> => {
    const response = await apiClient.post('/api/config/llm/providers', data)
    return response.data.provider
  },

  updateProvider: async (providerId: number, data: Partial<CreateProviderRequest>): Promise<LLMProvider> => {
    const response = await apiClient.put(`/api/config/llm/providers/${providerId}`, data)
    return response.data.provider
  },

  deleteProvider: async (providerId: number): Promise<void> => {
    await apiClient.delete(`/api/config/llm/providers/${providerId}`)
  },

  testProviderConnection: async (providerId: number): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post(`/api/config/llm/providers/${providerId}/test`)
    return response.data
  },

  // Models
  getModels: async (params?: {
    provider_id?: number
    model_type?: string
    active_only?: boolean
  }): Promise<{ models: LLMModel[] }> => {
    const response = await apiClient.get('/api/config/llm/models', { params })
    return response.data
  },

  getModel: async (modelId: number): Promise<LLMModel> => {
    const response = await apiClient.get(`/api/config/llm/models/${modelId}`)
    return response.data
  },

  createModel: async (data: CreateModelRequest): Promise<LLMModel> => {
    const response = await apiClient.post('/api/config/llm/models', data)
    return response.data.model
  },

  updateModel: async (modelId: number, data: Partial<CreateModelRequest>): Promise<LLMModel> => {
    const response = await apiClient.put(`/api/config/llm/models/${modelId}`, data)
    return response.data.model
  },

  deleteModel: async (modelId: number): Promise<void> => {
    await apiClient.delete(`/api/config/llm/models/${modelId}`)
  },

  // Assignments
  getAssignments: async (): Promise<{ assignments: LLMAssignment[] }> => {
    const response = await apiClient.get('/api/config/llm/assignments')
    return response.data
  },

  getAssignment: async (useCase: string): Promise<LLMAssignment> => {
    const response = await apiClient.get(`/api/config/llm/assignments/${useCase}`)
    return response.data
  },

  updateAssignment: async (useCase: string, data: UpdateAssignmentRequest): Promise<LLMAssignment> => {
    const response = await apiClient.put(`/api/config/llm/assignments/${useCase}`, data)
    return response.data.assignment
  },

  // Test LLM
  testLLM: async (data: LLMTestRequest): Promise<LLMTestResponse> => {
    const response = await apiClient.post('/api/config/llm/test', data)
    return response.data
  },
}

export default llmApi

