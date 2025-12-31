import { apiClient } from './client'

export interface Task {
  id: number
  task_type: string
  title: string
  description?: string
  related_type?: string
  related_id?: number
  assignee_id?: number
  assignee_name?: string
  requester_id?: number
  requester_name?: string
  status: string
  priority: string
  resolution?: string
  resolved_at?: string
  due_date?: string
  created_at: string
  updated_at: string
}

export interface CreateTaskRequest {
  task_type: string
  title: string
  description?: string
  related_type?: string
  related_id?: number
  assignee_id?: number
  priority?: string
  due_date?: string
}

export interface UpdateTaskRequest {
  title?: string
  description?: string
  assignee_id?: number
  priority?: string
  status?: string
  due_date?: string
}

export interface TaskStats {
  by_status: Record<string, number>
  by_type: Record<string, number>
  overdue: number
  total_open: number
}

export const tasksApi = {
  // List tasks
  getTasks: async (params?: {
    status_filter?: string
    task_type?: string
    priority?: string
    assignee_id?: number
    limit?: number
    offset?: number
  }): Promise<{ total: number; tasks: Task[] }> => {
    const response = await apiClient.get('/api/tasks', { params })
    return response.data
  },

  // Get my tasks
  getMyTasks: async (params?: {
    status_filter?: string
    limit?: number
    offset?: number
  }): Promise<{ total: number; tasks: Task[] }> => {
    const response = await apiClient.get('/api/tasks/mine', { params })
    return response.data
  },

  // Create task
  createTask: async (data: CreateTaskRequest): Promise<Task> => {
    const response = await apiClient.post('/api/tasks', data)
    return response.data
  },

  // Get task detail
  getTask: async (taskId: number): Promise<Task> => {
    const response = await apiClient.get(`/api/tasks/${taskId}`)
    return response.data
  },

  // Update task
  updateTask: async (taskId: number, data: UpdateTaskRequest): Promise<Task> => {
    const response = await apiClient.put(`/api/tasks/${taskId}`, data)
    return response.data
  },

  // Resolve task
  resolveTask: async (taskId: number, resolution: string): Promise<Task> => {
    const response = await apiClient.post(`/api/tasks/${taskId}/resolve`, { resolution })
    return response.data
  },

  // Cancel task
  cancelTask: async (taskId: number): Promise<{ message: string }> => {
    const response = await apiClient.post(`/api/tasks/${taskId}/cancel`)
    return response.data
  },

  // Get task stats
  getTaskStats: async (): Promise<TaskStats> => {
    const response = await apiClient.get('/api/tasks/stats/summary')
    return response.data
  },
}

export default tasksApi

