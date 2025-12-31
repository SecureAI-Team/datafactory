import { apiClient } from './client'

// LLM types
export interface LLMProvider {
  id: number
  provider_code: string
  provider_name: string
  api_base_url?: string
  is_active: boolean
  is_default: boolean
  config: Record<string, unknown>
}

export interface LLMModel {
  id: number
  provider_id: number
  model_code: string
  model_name: string
  model_type: string
  capabilities: string[]
  context_window?: number
  max_output_tokens?: number
  is_active: boolean
  is_default: boolean
}

export interface ModelAssignment {
  use_case: string
  model_id: number
  fallback_model_id?: number
  config_override: Record<string, unknown>
}

// Integration types
export interface IntegrationStatus {
  name: string
  status: 'connected' | 'disconnected' | 'error'
  message?: string
  last_checked?: string
}

// System config types
export interface SystemConfig {
  id: number
  config_group: string
  config_key: string
  config_value?: string
  value_type: string
  description?: string
  is_secret: boolean
  is_editable: boolean
  default_value?: string
}

export interface FeatureFlag {
  key: string
  enabled: boolean
  description?: string
}

export const settingsApi = {
  // LLM Providers
  getProviders: async (): Promise<{ providers: LLMProvider[] }> => {
    const response = await apiClient.get('/api/config/llm/providers')
    return response.data
  },

  createProvider: async (data: Partial<LLMProvider>): Promise<LLMProvider> => {
    const response = await apiClient.post('/api/config/llm/providers', data)
    return response.data
  },

  updateProvider: async (providerId: number, data: Partial<LLMProvider>): Promise<LLMProvider> => {
    const response = await apiClient.put(`/api/config/llm/providers/${providerId}`, data)
    return response.data
  },

  testProvider: async (providerId: number): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post(`/api/config/llm/providers/${providerId}/test`)
    return response.data
  },

  // LLM Models
  getModels: async (): Promise<{ models: LLMModel[] }> => {
    const response = await apiClient.get('/api/config/llm/models')
    return response.data
  },

  updateModel: async (modelId: number, data: Partial<LLMModel>): Promise<LLMModel> => {
    const response = await apiClient.put(`/api/config/llm/models/${modelId}`, data)
    return response.data
  },

  // Model Assignments
  getAssignments: async (): Promise<{ assignments: ModelAssignment[] }> => {
    const response = await apiClient.get('/api/config/llm/assignments')
    return response.data
  },

  updateAssignment: async (useCase: string, data: Partial<ModelAssignment>): Promise<ModelAssignment> => {
    const response = await apiClient.put(`/api/config/llm/assignments/${useCase}`, data)
    return response.data
  },

  // Integration Status
  getIntegrations: async (): Promise<{ integrations: IntegrationStatus[] }> => {
    const response = await apiClient.get('/api/config/integrations')
    return response.data
  },

  testIntegration: async (service: string): Promise<IntegrationStatus> => {
    const response = await apiClient.post(`/api/config/integrations/${service}/test`)
    return response.data
  },

  // System Configs
  getSystemConfigs: async (group?: string): Promise<{ configs: SystemConfig[] }> => {
    const url = group ? `/api/config/system/${group}` : '/api/config/system'
    const response = await apiClient.get(url)
    return response.data
  },

  updateSystemConfig: async (group: string, key: string, value: string): Promise<SystemConfig> => {
    const response = await apiClient.put(`/api/config/system/${group}/${key}`, { value })
    return response.data
  },

  // Feature Flags
  getFeatures: async (): Promise<{ features: FeatureFlag[] }> => {
    const response = await apiClient.get('/api/config/features')
    return response.data
  },

  toggleFeature: async (key: string, enabled: boolean): Promise<FeatureFlag> => {
    const response = await apiClient.put(`/api/config/features/${key}`, { enabled })
    return response.data
  },
}

export default settingsApi

