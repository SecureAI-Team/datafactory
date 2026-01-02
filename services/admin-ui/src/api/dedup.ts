import { apiClient } from './client'

export interface KUCandidate {
  id: string
  title: string
  summary: string
  ku_type: string
  product_id?: string
  version: number
  status: string
}

export interface DedupGroup {
  group_id: string
  ku_ids: string[]
  similarity_score: number
  status: string
  merge_result_ku_id?: number
  reviewed_by?: string
  reviewed_at?: string
  created_at: string
  kus?: KUCandidate[]  // 详情查询时返回
}

export interface DedupStats {
  total: number
  pending: number
  approved: number
  merged: number
  dismissed: number
}

export interface CreateDedupGroupRequest {
  ku_ids: string[]
  similarity_score?: number
  creator: string
}

export const dedupApi = {
  // 手动创建重复组
  create: async (data: CreateDedupGroupRequest): Promise<DedupGroup> => {
    const response = await apiClient.post('/api/v1/dedup/create', data)
    return response.data
  },

  // 获取待处理的重复组
  getPending: async (limit: number = 20): Promise<DedupGroup[]> => {
    const response = await apiClient.get('/api/v1/dedup/pending', { params: { limit } })
    return response.data
  },

  // 获取所有重复组
  getAll: async (params?: { status?: string; limit?: number }): Promise<DedupGroup[]> => {
    const response = await apiClient.get('/api/v1/dedup/all', { params })
    return response.data
  },

  // 获取重复组详情
  getGroupDetails: async (groupId: string): Promise<{ group_id: string; similarity_score: number; status: string; kus: KUCandidate[] }> => {
    const response = await apiClient.get(`/api/v1/dedup/group/${groupId}/details`)
    return response.data
  },

  // 批准合并
  approve: async (groupId: string, reviewer: string): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post('/api/v1/dedup/approve', {
      group_id: groupId,
      reviewer,
    })
    return response.data
  },

  // 标记为非重复
  dismiss: async (groupId: string, reviewer: string, reason?: string): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post('/api/v1/dedup/dismiss', {
      group_id: groupId,
      reviewer,
      reason,
    })
    return response.data
  },

  // 执行合并
  executeMerge: async (groupId: string, strategy: string = 'comprehensive'): Promise<{
    success: boolean
    message: string
    merged_ku_id: number
    source_ku_ids: string[]
  }> => {
    const response = await apiClient.post(`/api/v1/dedup/group/${groupId}/merge`, { strategy })
    return response.data
  },

  // 获取统计数据
  getStats: async (): Promise<DedupStats> => {
    const response = await apiClient.get('/api/v1/dedup/stats')
    return response.data
  },

  // 查找相似 KU
  findSimilar: async (kuId: number, params?: { min_similarity?: number; limit?: number }): Promise<SimilarKU[]> => {
    const response = await apiClient.get(`/api/v1/dedup/similar/${kuId}`, { params })
    return response.data
  },
}

export interface SimilarKU {
  id: string
  title: string
  summary: string
  ku_type?: string
  product_id?: string
  similarity_score: number
}

export default dedupApi

