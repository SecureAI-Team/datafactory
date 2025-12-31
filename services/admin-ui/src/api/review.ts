import { apiClient } from './client'

export interface Contribution {
  id: number
  contributor_id: number
  contributor_name?: string
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
  review_comment?: string
  reviewed_at?: string
  created_at: string
}

export interface ReviewQueueResponse {
  total: number
  contributions: Contribution[]
}

export interface ReviewStatsResponse {
  total_pending: number
  total_approved: number
  total_rejected: number
  needs_info: number
  pending_by_type: Record<string, number>
}

export const reviewApi = {
  getQueue: async (params?: {
    status_filter?: string
    contribution_type?: string
    ku_type?: string
    limit?: number
    offset?: number
  }): Promise<ReviewQueueResponse> => {
    const response = await apiClient.get('/api/review/queue', { params })
    return response.data
  },

  getDetail: async (contributionId: number): Promise<Contribution> => {
    const response = await apiClient.get(`/api/review/${contributionId}`)
    return response.data
  },

  approve: async (contributionId: number, comment?: string): Promise<void> => {
    await apiClient.post(`/api/review/${contributionId}/approve`, { comment })
  },

  reject: async (contributionId: number, reason: string): Promise<void> => {
    await apiClient.post(`/api/review/${contributionId}/reject`, { reason })
  },

  requestInfo: async (contributionId: number, questions: string): Promise<void> => {
    await apiClient.post(`/api/review/${contributionId}/request-info`, { questions })
  },

  batchReview: async (contributionIds: number[], action: 'approve' | 'reject', comment?: string): Promise<{ processed: number }> => {
    const response = await apiClient.post('/api/review/batch', {
      contribution_ids: contributionIds,
      action,
      comment,
    })
    return response.data
  },

  getStats: async (): Promise<ReviewStatsResponse> => {
    const response = await apiClient.get('/api/review/stats/summary')
    return response.data
  },
}

export default reviewApi

