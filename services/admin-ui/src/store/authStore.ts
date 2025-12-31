import { create } from 'zustand'

interface User {
  id: number
  username: string
  email: string
  display_name?: string
  role: string
  department?: string
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  getUser: () => User | null
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: (() => {
    try {
      const stored = localStorage.getItem('admin_user')
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })(),
  
  isAuthenticated: !!localStorage.getItem('admin_access_token'),
  
  getUser: () => {
    const state = get()
    if (state.user) return state.user
    
    try {
      const stored = localStorage.getItem('admin_user')
      const user = stored ? JSON.parse(stored) : null
      if (user) {
        set({ user })
      }
      return user
    } catch {
      return null
    }
  },
}))

