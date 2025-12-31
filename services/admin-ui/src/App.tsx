import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import AdminLayout from './components/layout/AdminLayout'
import Dashboard from './pages/Dashboard'
import Review from './pages/Review'
import Config from './pages/Config'
import Users from './pages/Users'
import Settings from './pages/Settings'
import Tasks from './pages/Tasks'
import Quality from './pages/Quality'
import Login from './pages/Login'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  
  useEffect(() => {
    // Check if user is logged in
    const token = localStorage.getItem('admin_access_token')
    setIsAuthenticated(!!token)
  }, [])
  
  if (!isAuthenticated) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login onLogin={() => setIsAuthenticated(true)} />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    )
  }
  
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AdminLayout onLogout={() => setIsAuthenticated(false)} />}>
          <Route index element={<Dashboard />} />
          <Route path="review" element={<Review />} />
          <Route path="config" element={<Config />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="quality" element={<Quality />} />
          <Route path="users" element={<Users />} />
          <Route path="settings/*" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App

