import { apiClient } from './client'

// Types
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
  validation?: {
    min?: number
    max?: number
    pattern?: string
    required?: boolean
  }
  required?: boolean
  dependsOn?: {
    stepId: string
    values: string[]
  }
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

export interface InteractionSession {
  id: number
  session_id: string
  conversation_id: string
  flow_id: string
  current_step: number
  collected_answers: Record<string, string | string[]>
  status: 'active' | 'completed' | 'cancelled'
  created_at: string
  updated_at: string
}

export interface StartInteractionResponse {
  session: InteractionSession
  flow: {
    flow_id: string
    name: string
    total_steps: number
  }
  current_question: InteractionStep | null
}

export interface AnswerInteractionResponse {
  session: InteractionSession
  completed: boolean
  current_question?: InteractionStep | null
  progress?: {
    answered: number
    total: number
  }
  collected_answers?: Record<string, string | string[]>
  labeled_answers?: Record<string, string | string[]>  // Human-readable version
  on_complete?: string
}

export interface ActiveSessionResponse {
  session: InteractionSession | null
  flow?: {
    flow_id: string
    name: string
  }
  current_question?: InteractionStep | null
}

export const interactionApi = {
  // Get all flows
  getFlows: async (params?: { scenario_id?: string; is_active?: boolean }): Promise<{
    flows: InteractionFlow[]
    total: number
  }> => {
    const response = await apiClient.get('/api/config/interaction-flows', { params })
    return response.data
  },

  // Get single flow
  getFlow: async (flowId: string): Promise<InteractionFlow> => {
    const response = await apiClient.get(`/api/config/interaction-flows/${flowId}`)
    return response.data
  },

  // Start interaction session
  startSession: async (
    conversationId: string,
    flowId: string
  ): Promise<StartInteractionResponse> => {
    const response = await apiClient.post(
      '/api/config/interaction-sessions/start',
      { flow_id: flowId },
      { params: { conversation_id: conversationId } }
    )
    return response.data
  },

  // Submit answer
  submitAnswer: async (
    sessionId: string,
    stepId: string,
    answer: string | string[]
  ): Promise<AnswerInteractionResponse> => {
    const response = await apiClient.post(
      `/api/config/interaction-sessions/${sessionId}/answer`,
      { step_id: stepId, answer }
    )
    return response.data
  },

  // Cancel session
  cancelSession: async (sessionId: string): Promise<{ message: string }> => {
    const response = await apiClient.post(
      `/api/config/interaction-sessions/${sessionId}/cancel`
    )
    return response.data
  },

  // Get active session for conversation
  getActiveSession: async (conversationId: string): Promise<ActiveSessionResponse> => {
    const response = await apiClient.get(
      `/api/config/interaction-sessions/${conversationId}/active`
    )
    return response.data
  },

  // Check if a message should trigger an interaction flow
  checkTrigger: (message: string, flows: InteractionFlow[]): InteractionFlow | null => {
    const lowerMessage = message.toLowerCase()
    
    for (const flow of flows) {
      if (!flow.is_active) continue
      
      for (const pattern of flow.trigger_patterns) {
        if (lowerMessage.includes(pattern.toLowerCase())) {
          return flow
        }
      }
    }
    
    return null
  },
}

export default interactionApi

