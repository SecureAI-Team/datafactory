import { apiClient } from './client'

export interface User {
  id: number
  username: string
  email: string
  display_name?: string
  role: string
  department?: string
  is_active: boolean
  last_login_at?: string
  created_at: string
}

export interface CreateUserRequest {
  username: string
  email: string
  password: string
  display_name?: string
  role: string
  department?: string
}

export interface UpdateUserRequest {
  email?: string
  display_name?: string
  role?: string
  department?: string
  is_active?: boolean
}

export interface UsersListResponse {
  users: User[]
  total: number
}

export const usersApi = {
  list: async (params?: { limit?: number; offset?: number; role?: string }): Promise<UsersListResponse> => {
    const response = await apiClient.get('/api/users', { params })
    return response.data
  },

  get: async (userId: number): Promise<User> => {
    const response = await apiClient.get(`/api/users/${userId}`)
    return response.data
  },

  create: async (data: CreateUserRequest): Promise<User> => {
    const response = await apiClient.post('/api/users', data)
    return response.data
  },

  update: async (userId: number, data: UpdateUserRequest): Promise<User> => {
    const response = await apiClient.put(`/api/users/${userId}`, data)
    return response.data
  },

  delete: async (userId: number): Promise<void> => {
    await apiClient.delete(`/api/users/${userId}`)
  },

  getStats: async (userId: number): Promise<{ contributions: number; queries: number }> => {
    const response = await apiClient.get(`/api/users/${userId}/stats`)
    return response.data
  },
}

export default usersApi

