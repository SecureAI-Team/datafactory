import { apiClient } from './client'

// ==================== Types ====================

export interface TestCase {
  id: number
  name: string
  category: 'rag' | 'llm' | 'e2e'
  query: string
  expected_ku_ids: string[]
  expected_answer?: string
  evaluation_criteria: Record<string, unknown>
  tags: string[]
  is_active: boolean
  created_by?: string
  created_at?: string
  updated_at?: string
}

export interface TestCaseCreate {
  name: string
  category: 'rag' | 'llm' | 'e2e'
  query: string
  expected_ku_ids?: string[]
  expected_answer?: string
  evaluation_criteria?: Record<string, unknown>
  tags?: string[]
  is_active?: boolean
}

export interface TestCaseUpdate {
  name?: string
  category?: 'rag' | 'llm' | 'e2e'
  query?: string
  expected_ku_ids?: string[]
  expected_answer?: string
  evaluation_criteria?: Record<string, unknown>
  tags?: string[]
  is_active?: boolean
}

export interface TestRun {
  id: number
  run_id: string
  status: 'running' | 'completed' | 'failed'
  total_cases: number
  passed_cases: number
  failed_cases: number
  review_cases: number
  pass_rate?: number
  started_at?: string
  completed_at?: string
  triggered_by?: string
}

export interface TestRunCreate {
  category_filter?: string
  tag_filter?: string[]
  case_ids?: number[]
}

export interface LLMEvaluation {
  accuracy?: number
  completeness?: number
  relevance?: number
  clarity?: number
  overall?: number
  comment?: string
  faithfulness?: number
  answer_relevancy?: number
  context_precision?: number
  context_recall?: number
  [key: string]: unknown
}

export interface TestResult {
  id: number
  run_id: number
  case_id: number
  case_name?: string
  case_query?: string
  case_category?: string
  actual_answer?: string
  retrieved_ku_ids: string[]
  retrieval_score?: number
  answer_score?: number
  llm_evaluation?: LLMEvaluation
  manual_review: 'pending' | 'pass' | 'fail'
  manual_comment?: string
  reviewed_by?: string
  reviewed_at?: string
  execution_time_ms?: number
  status: 'pass' | 'fail' | 'review' | 'pending'
  error_message?: string
  created_at?: string
}

export interface ManualReview {
  review: 'pass' | 'fail'
  comment?: string
}

export interface RegressionStats {
  total_cases: number
  cases_by_category: Record<string, number>
  total_runs: number
  avg_pass_rate: number
  pending_reviews: number
  recent_runs: TestRun[]
}

export interface EvaluatorHealth {
  evaluator_healthy: boolean
  evaluator_url: string
}

// ==================== API Functions ====================

export const regressionApi = {
  // Test Cases
  listCases: async (params?: {
    category?: string
    tag?: string
    is_active?: boolean
    skip?: number
    limit?: number
  }): Promise<TestCase[]> => {
    const response = await apiClient.get('/api/v1/regression/cases', { params })
    return response.data
  },

  getCase: async (caseId: number): Promise<TestCase> => {
    const response = await apiClient.get(`/api/v1/regression/cases/${caseId}`)
    return response.data
  },

  createCase: async (data: TestCaseCreate): Promise<TestCase> => {
    const response = await apiClient.post('/api/v1/regression/cases', data)
    return response.data
  },

  updateCase: async (caseId: number, data: TestCaseUpdate): Promise<TestCase> => {
    const response = await apiClient.put(`/api/v1/regression/cases/${caseId}`, data)
    return response.data
  },

  deleteCase: async (caseId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/regression/cases/${caseId}`)
  },

  importCases: async (cases: TestCaseCreate[]): Promise<{
    imported: number
    total: number
    errors: Array<{ index: number; error: string }>
  }> => {
    const response = await apiClient.post('/api/v1/regression/cases/import', { cases })
    return response.data
  },

  // Test Runs
  listRuns: async (params?: {
    status?: string
    skip?: number
    limit?: number
  }): Promise<TestRun[]> => {
    const response = await apiClient.get('/api/v1/regression/runs', { params })
    return response.data
  },

  getRun: async (runId: number): Promise<TestRun> => {
    const response = await apiClient.get(`/api/v1/regression/runs/${runId}`)
    return response.data
  },

  createRun: async (data: TestRunCreate): Promise<TestRun> => {
    const response = await apiClient.post('/api/v1/regression/runs', data)
    return response.data
  },

  getRunResults: async (runId: number, params?: {
    status?: string
    manual_review?: string
  }): Promise<TestResult[]> => {
    const response = await apiClient.get(`/api/v1/regression/runs/${runId}/results`, { params })
    return response.data
  },

  // Manual Review
  submitReview: async (resultId: number, data: ManualReview): Promise<{
    message: string
    status: string
  }> => {
    const response = await apiClient.post(`/api/v1/regression/results/${resultId}/review`, data)
    return response.data
  },

  // Statistics
  getStats: async (): Promise<RegressionStats> => {
    const response = await apiClient.get('/api/v1/regression/stats')
    return response.data
  },

  // Evaluator Health
  checkEvaluatorHealth: async (): Promise<EvaluatorHealth> => {
    const response = await apiClient.get('/api/v1/regression/evaluator/health')
    return response.data
  },
}

export default regressionApi

