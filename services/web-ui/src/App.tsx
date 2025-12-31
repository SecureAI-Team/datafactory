import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import { authApi } from './api/auth'
import Layout from './components/layout/Layout'
import Home from './pages/Home'
import Login from './pages/Login'
import MyData from './pages/MyData'
import Settings from './pages/Settings'
import SharedChat from './pages/SharedChat'
import Upload from './pages/Upload'
import { Loader2 } from 'lucide-react'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, accessToken, logout, updateUser } = useAuthStore()
  const [isValidating, setIsValidating] = useState(true)
  const [isValid, setIsValid] = useState(false)
  
  useEffect(() => {
    const validateToken = async () => {
      if (!accessToken) {
        setIsValidating(false)
        setIsValid(false)
        return
      }
      
      try {
        // Validate token by calling /api/auth/me
        const user = await authApi.getMe()
        // Update user info in case it changed
        updateUser(user)
        setIsValid(true)
      } catch (error) {
        // Token is invalid - logout
        console.error('Token validation failed:', error)
        logout()
        setIsValid(false)
      } finally {
        setIsValidating(false)
      }
    }
    
    validateToken()
  }, [accessToken, logout, updateUser])
  
  // Show loading while validating
  if (isValidating) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-950">
        <div className="text-center">
          <Loader2 className="animate-spin text-primary-500 mx-auto mb-4" size={40} />
          <p className="text-dark-400">验证登录状态...</p>
        </div>
      </div>
    )
  }
  
  if (!isAuthenticated || !isValid) {
    return <Navigate to="/login" replace />
  }
  
  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 公开路由 */}
        <Route path="/login" element={<Login />} />
        <Route path="/share/:token" element={<SharedChat />} />
        
        {/* 受保护路由 */}
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route index element={<Home />} />
          <Route path="c/:conversationId" element={<Home />} />
          <Route path="my" element={<MyData />} />
          <Route path="upload" element={<Upload />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        
        {/* 404 重定向 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App

