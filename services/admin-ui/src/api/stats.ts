import { apiClient } from './client'

export interface OverviewStats {
  today_processed: number
  total_kus: number
  published_kus: number
  pending_reviews: number
  failed_runs: number
  active_users: number
}

export interface PipelineStats {
  daily_stats: Record<string, { success: number; failed: number; running: number }>
  recent_runs: Array<{
    id: number
    pipeline_name: string
    status: string
    started_at?: string
    duration_seconds?: number
    input_count?: number
    output_count?: number
  }>
}

export interface QualityStats {
  dq_pass_rate: number
  total_dq_runs: number
  ku_type_distribution: Record<string, number>
  ku_status_distribution: Record<string, number>
}

export interface ContributionStats {
  by_status: Record<string, number>
  by_type: Record<string, number>
  daily_trend: Array<{ date: string; count: number }>
  top_contributors: Array<{
    user_id: number
    username: string
    display_name?: string
    total: number
    approved: number
  }>
}

export interface Activity {
  type: string
  status: string
  message: string
  time?: string
}

export interface UsageStats {
  daily_conversations: Array<{ date: string; count: number }>
  daily_messages: Array<{ date: string; count: number }>
  daily_active_users: Array<{ date: string; count: number }>
}

export interface FeedbackStats {
  positive_rate: number
  negative_rate: number
  pending_count: number
  total_feedback: number
  negative_feedback: Array<{
    id: string
    query: string
    feedback: string
    reason: string
    date: string
    conversation_id?: string
  }>
}

export interface DQRunItem {
  id: number
  ku_id: string
  passed: boolean
  reasons: string[]
  date: string
  details?: {
    title?: string
    ku_type?: string
    checks?: Array<{ name: string; passed: boolean; message?: string }>
  }
}

export interface DQRunsResponse {
  runs: DQRunItem[]
}

export const statsApi = {
  getOverview: async (): Promise<OverviewStats> => {
    const response = await apiClient.get('/api/stats/overview')
    return response.data
  },

  getPipeline: async (days: number = 7): Promise<PipelineStats> => {
    const response = await apiClient.get('/api/stats/pipeline', { params: { days } })
    return response.data
  },

  getQuality: async (): Promise<QualityStats> => {
    const response = await apiClient.get('/api/stats/quality')
    return response.data
  },

  getContributions: async (days: number = 30): Promise<ContributionStats> => {
    const response = await apiClient.get('/api/stats/contributions', { params: { days } })
    return response.data
  },

  getRecentActivity: async (limit: number = 20): Promise<{ activities: Activity[] }> => {
    const response = await apiClient.get('/api/stats/recent-activity', { params: { limit } })
    return response.data
  },

  getUsage: async (days: number = 7): Promise<UsageStats> => {
    const response = await apiClient.get('/api/stats/usage', { params: { days } })
    return response.data
  },

  getFeedback: async (days: number = 30): Promise<FeedbackStats> => {
    const response = await apiClient.get('/api/stats/feedback', { params: { days } })
    return response.data
  },

  getDQRuns: async (params?: { limit?: number; passed?: boolean }): Promise<DQRunsResponse> => {
    const response = await apiClient.get('/api/stats/dq-runs', { params })
    return response.data
  },
}

export default statsApi

