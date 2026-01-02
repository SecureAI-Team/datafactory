import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, LogOut, Settings, ChevronDown, Folder, AlertCircle, CheckCircle, XCircle } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../../store/authStore'
import { authApi } from '../../api/auth'
import { contributeApi, Notification } from '../../api/contribute'

export default function Header() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, logout, refreshToken } = useAuthStore()
  const [showDropdown, setShowDropdown] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const notificationRef = useRef<HTMLDivElement>(null)
  
  // Fetch notifications
  const { data: notificationsData } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => contributeApi.getNotifications({ limit: 10 }),
    refetchInterval: 30000, // Refetch every 30 seconds
    staleTime: 10000,
  })

  const unreadCount = notificationsData?.unread_count || 0
  const notifications = notificationsData?.notifications || []

  // Mark notification as read mutation
  const markReadMutation = useMutation({
    mutationFn: (notificationId: number) => contributeApi.markNotificationRead(notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  // Mark all as read mutation
  const markAllReadMutation = useMutation({
    mutationFn: () => contributeApi.markAllNotificationsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
  
  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false)
      }
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) {
        setShowNotifications(false)
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleNotificationClick = (notification: Notification) => {
    // Mark as read
    if (!notification.is_read) {
      markReadMutation.mutate(notification.id)
    }
    
    // Navigate to related item
    if (notification.related_type === 'contribution' && notification.related_id) {
      navigate('/my')
    }
    
    setShowNotifications(false)
  }

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'approved':
        return <CheckCircle size={16} className="text-green-400" />
      case 'rejected':
        return <XCircle size={16} className="text-red-400" />
      case 'needs_info':
        return <AlertCircle size={16} className="text-orange-400" />
      default:
        return <Bell size={16} className="text-primary-400" />
    }
  }
  
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
        <div className="relative" ref={notificationRef}>
          <button 
            className="btn-ghost p-2 relative"
            onClick={() => setShowNotifications(!showNotifications)}
          >
            <Bell size={20} />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 min-w-[16px] h-4 px-1 bg-red-500 rounded-full text-[10px] text-white flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
          
          {/* Notifications Dropdown */}
          {showNotifications && (
            <div className="absolute right-0 top-full mt-1 w-80 bg-dark-800 border border-dark-700 rounded-lg shadow-xl z-50 animate-fade-in">
              <div className="flex items-center justify-between px-4 py-3 border-b border-dark-700">
                <h3 className="font-medium">通知</h3>
                {unreadCount > 0 && (
                  <button 
                    onClick={() => markAllReadMutation.mutate()}
                    className="text-xs text-primary-400 hover:text-primary-300"
                  >
                    全部已读
                  </button>
                )}
              </div>
              
              <div className="max-h-80 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="px-4 py-8 text-center text-dark-400 text-sm">
                    暂无通知
                  </div>
                ) : (
                  notifications.map((notification) => (
                    <button
                      key={notification.id}
                      onClick={() => handleNotificationClick(notification)}
                      className={`w-full px-4 py-3 flex items-start gap-3 text-left hover:bg-dark-700 border-b border-dark-700 last:border-0 ${
                        !notification.is_read ? 'bg-dark-750' : ''
                      }`}
                    >
                      <div className="mt-0.5">
                        {getNotificationIcon(notification.notification_type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm ${!notification.is_read ? 'font-medium' : ''}`}>
                          {notification.title}
                        </p>
                        {notification.message && (
                          <p className="text-xs text-dark-400 mt-0.5 line-clamp-2">
                            {notification.message}
                          </p>
                        )}
                        <p className="text-xs text-dark-500 mt-1">
                          {notification.created_at ? new Date(notification.created_at).toLocaleString('zh-CN') : ''}
                        </p>
                      </div>
                      {!notification.is_read && (
                        <div className="w-2 h-2 bg-primary-500 rounded-full mt-2" />
                      )}
                    </button>
                  ))
                )}
              </div>
              
              {notifications.length > 0 && (
                <div className="px-4 py-2 border-t border-dark-700">
                  <button 
                    onClick={() => {
                      navigate('/my')
                      setShowNotifications(false)
                    }}
                    className="w-full text-center text-xs text-primary-400 hover:text-primary-300 py-1"
                  >
                    查看我的贡献
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
        
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

