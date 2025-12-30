import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, User, LogOut, Settings, ChevronDown, Folder } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { authApi } from '../../api/auth'

export default function Header() {
  const navigate = useNavigate()
  const { user, logout, refreshToken } = useAuthStore()
  const [showDropdown, setShowDropdown] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  
  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false)
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])
  
  const handleLogout = async () => {
    try {
      if (refreshToken) {
        await authApi.logout(refreshToken)
      }
    } catch {
      // Ignore errors
    } finally {
      logout()
      navigate('/login')
    }
  }
  
  return (
    <header className="h-14 bg-dark-900 border-b border-dark-800 flex items-center justify-between px-4">
      {/* Left: App Title */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
          <span className="text-white font-bold text-sm">AI</span>
        </div>
        <h1 className="font-semibold text-lg">智能销售助手</h1>
      </div>
      
      {/* Right: User Actions */}
      <div className="flex items-center gap-2">
        {/* Notifications */}
        <button className="btn-ghost p-2 relative">
          <Bell size={20} />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
        </button>
        
        {/* User Menu */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            className="flex items-center gap-2 btn-ghost px-3 py-1.5"
          >
            <div className="w-7 h-7 rounded-full bg-primary-600 flex items-center justify-center">
              <span className="text-white text-sm font-medium">
                {user?.display_name?.[0] || user?.username?.[0] || 'U'}
              </span>
            </div>
            <span className="text-sm font-medium">{user?.display_name || user?.username}</span>
            <ChevronDown size={16} className={showDropdown ? 'rotate-180 transition-transform' : 'transition-transform'} />
          </button>
          
          {/* Dropdown Menu */}
          {showDropdown && (
            <div className="absolute right-0 top-full mt-1 w-56 bg-dark-800 border border-dark-700 rounded-lg shadow-xl py-1 z-50 animate-fade-in">
              <div className="px-4 py-3 border-b border-dark-700">
                <p className="text-sm font-medium">{user?.display_name || user?.username}</p>
                <p className="text-xs text-dark-400">{user?.email}</p>
                <p className="text-xs text-primary-400 mt-1 capitalize">{user?.role}</p>
              </div>
              
              <button
                onClick={() => {
                  navigate('/my')
                  setShowDropdown(false)
                }}
                className="flex items-center gap-3 w-full px-4 py-2.5 text-sm hover:bg-dark-700"
              >
                <Folder size={16} />
                我的资料
              </button>
              
              <button
                onClick={() => {
                  navigate('/settings')
                  setShowDropdown(false)
                }}
                className="flex items-center gap-3 w-full px-4 py-2.5 text-sm hover:bg-dark-700"
              >
                <Settings size={16} />
                个人设置
              </button>
              
              <div className="h-px bg-dark-700 my-1" />
              
              <button
                onClick={handleLogout}
                className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-red-400 hover:bg-dark-700"
              >
                <LogOut size={16} />
                退出登录
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

