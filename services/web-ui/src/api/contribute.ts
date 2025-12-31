import { apiClient } from './client'

export interface Contribution {
  id: number
  contributor_id: number
  contribution_type: string
  title?: string
  description?: string
  file_name?: string
  file_size?: number
  mime_type?: string
  ku_type_code?: string
  product_id?: string
  tags: string[]
  visibility: string
  trigger_type?: string
  conversation_id?: string
  query_text?: string
  status: string
  processed_ku_id?: number
  reviewer_id?: number
  review_comment?: string
  reviewed_at?: string
  created_at: string
  updated_at?: string
}

export interface ContributionStats {
  total_contributions: number
  approved_count: number
  rejected_count: number
  pending_count: number
  citation_count: number
  achievements: string[]
  streak_days: number
}

export interface ContributionsListResponse {
  total: number
  contributions: Contribution[]
}

export interface LeaderboardEntry {
  user_id: number
  username: string
  display_name?: string
  total_contributions: number
  approved_count: number
  citation_count: number
}

export interface DraftKURequest {
  title: string
  description?: string
  content_json?: Record<string, unknown>
  ku_type_code: string
  product_id?: string
  tags?: string[]
  visibility?: string
  expiry_date?: string
  conversation_id?: string
  query_text?: string
  trigger_type?: string
}

export interface SignalRequest {
  title: string
  description: string
  content_json: Record<string, unknown>
  product_id?: string
  tags?: string[]
  conversation_id?: string
  query_text?: string
}

export interface ClassifyRequest {
  filename: string
  content: string
  mime_type?: string
}

export interface ClassifyResponse {
  ku_type_code: string
  ku_type_name: string
  product_id?: string
  tags: string[]
  confidence: number
  reason: string
}

export const contributeApi = {
  uploadFile: async (file: File, metadata: {
    title?: string
    description?: string
    ku_type_code: string
    product_id?: string
    tags?: string[]
    visibility?: string
    conversation_id?: string
    query_text?: string
    trigger_type?: string
  }): Promise<Contribution> => {
    const formData = new FormData()
    formData.append('file', file)
    
    if (metadata.title) formData.append('title', metadata.title)
    if (metadata.description) formData.append('description', metadata.description)
    formData.append('ku_type_code', metadata.ku_type_code)
    if (metadata.product_id) formData.append('product_id', metadata.product_id)
    if (metadata.tags) formData.append('tags', JSON.stringify(metadata.tags))
    if (metadata.visibility) formData.append('visibility', metadata.visibility)
    if (metadata.conversation_id) formData.append('conversation_id', metadata.conversation_id)
    if (metadata.query_text) formData.append('query_text', metadata.query_text)
    if (metadata.trigger_type) formData.append('trigger_type', metadata.trigger_type)
    
    const response = await apiClient.post('/api/contribute/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  saveDraft: async (data: DraftKURequest): Promise<Contribution> => {
    const response = await apiClient.post('/api/contribute/draft', data)
    return response.data
  },

  saveSignal: async (data: SignalRequest): Promise<Contribution> => {
    const response = await apiClient.post('/api/contribute/signal', data)
    return response.data
  },

  getMine: async (params?: { status_filter?: string; limit?: number; offset?: number }): Promise<ContributionsListResponse> => {
    const response = await apiClient.get('/api/contribute/mine', { params })
    return response.data
  },

  getStats: async (): Promise<ContributionStats> => {
    const response = await apiClient.get('/api/contribute/stats')
    return response.data
  },

  get: async (contributionId: number): Promise<Contribution> => {
    const response = await apiClient.get(`/api/contribute/${contributionId}`)
    return response.data
  },

  update: async (contributionId: number, data: {
    title?: string
    description?: string
    content_json?: Record<string, unknown>
    tags?: string[]
    visibility?: string
  }): Promise<Contribution> => {
    const response = await apiClient.put(`/api/contribute/${contributionId}`, data)
    return response.data
  },

  delete: async (contributionId: number): Promise<void> => {
    await apiClient.delete(`/api/contribute/${contributionId}`)
  },

  getLeaderboard: async (limit: number = 10): Promise<{ leaderboard: LeaderboardEntry[] }> => {
    const response = await apiClient.get('/api/contribute/leaderboard', { params: { limit } })
    return response.data
  },

  // Supplement a contribution that needs more info
  supplement: async (contributionId: number, data: {
    additional_info: string
    content_json?: Record<string, unknown>
    file_path?: string
  }): Promise<Contribution> => {
    const response = await apiClient.put(`/api/contribute/${contributionId}/supplement`, data)
    return response.data
  },

  // Classify material using LLM
  classify: async (data: ClassifyRequest): Promise<ClassifyResponse> => {
    const response = await apiClient.post('/api/contribute/classify', data)
    return response.data
  },
}

export default contributeApi

