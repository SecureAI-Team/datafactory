import apiClient from './client'
import { User } from '../store/authStore'

interface LoginRequest {
  username: string
  password: string
}

interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

interface RefreshResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/api/auth/login', data)
    return response.data
  },
  
  logout: async (refreshToken: string): Promise<void> => {
    await apiClient.post('/api/auth/logout', { refresh_token: refreshToken })
  },
  
  refresh: async (refreshToken: string): Promise<RefreshResponse> => {
    const response = await apiClient.post<RefreshResponse>('/api/auth/refresh', {
      refresh_token: refreshToken,
    })
    return response.data
  },
  
  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/api/auth/me')
    return response.data
  },
  
  changePassword: async (oldPassword: string, newPassword: string): Promise<void> => {
    await apiClient.put('/api/auth/password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
  },
}

