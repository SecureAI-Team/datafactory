import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { User, Lock, Bell, Palette, Save, Loader2, Check } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { authApi } from '../api/auth'
import clsx from 'clsx'

const tabs = [
  { id: 'profile', icon: User, label: '个人信息' },
  { id: 'password', icon: Lock, label: '修改密码' },
  { id: 'notifications', icon: Bell, label: '通知设置' },
  { id: 'appearance', icon: Palette, label: '外观设置' },
]

export default function Settings() {
  const [activeTab, setActiveTab] = useState('profile')
  const { user, updateUser } = useAuthStore()
  
  // Profile form
  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [profileSaved, setProfileSaved] = useState(false)
  
  // Password form
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [passwordSuccess, setPasswordSuccess] = useState(false)
  
  const changePasswordMutation = useMutation({
    mutationFn: () => authApi.changePassword(oldPassword, newPassword),
    onSuccess: () => {
      setPasswordSuccess(true)
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setTimeout(() => setPasswordSuccess(false), 3000)
    },
    onError: (err: Error) => {
      setPasswordError(err.message || '密码修改失败')
    },
  })
  
  const handleSaveProfile = () => {
    updateUser({ display_name: displayName })
    setProfileSaved(true)
    setTimeout(() => setProfileSaved(false), 3000)
  }
  
  const handleChangePassword = () => {
    setPasswordError('')
    
    if (newPassword !== confirmPassword) {
      setPasswordError('两次输入的密码不一致')
      return
    }
    
    if (newPassword.length < 8) {
      setPasswordError('密码长度至少为8位')
      return
    }
    
    changePasswordMutation.mutate()
  }
  
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-8">个人设置</h1>
        
        <div className="flex gap-8">
          {/* Sidebar */}
          <div className="w-48 shrink-0">
            <nav className="space-y-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={clsx(
                    'w-full sidebar-item',
                    activeTab === tab.id && 'active'
                  )}
                >
                  <tab.icon size={18} />
                  <span>{tab.label}</span>
                </button>
              ))}
            </nav>
          </div>
          
          {/* Content */}
          <div className="flex-1">
            {activeTab === 'profile' && (
              <div className="card p-6">
                <h2 className="text-lg font-semibold mb-6">个人信息</h2>
                
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-dark-300 mb-2">
                      用户名
                    </label>
                    <input
                      type="text"
                      value={user?.username || ''}
                      disabled
                      className="input bg-dark-800/50 cursor-not-allowed"
                    />
                    <p className="text-xs text-dark-500 mt-1">用户名不可修改</p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-dark-300 mb-2">
                      显示名称
                    </label>
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      className="input"
                      placeholder="您的显示名称"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-dark-300 mb-2">
                      邮箱
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="input"
                      placeholder="your@email.com"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-dark-300 mb-2">
                      角色
                    </label>
                    <input
                      type="text"
                      value={user?.role || ''}
                      disabled
                      className="input bg-dark-800/50 cursor-not-allowed capitalize"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-dark-300 mb-2">
                      部门
                    </label>
                    <input
                      type="text"
                      value={user?.department || ''}
                      disabled
                      className="input bg-dark-800/50 cursor-not-allowed"
                    />
                  </div>
                  
                  <button
                    onClick={handleSaveProfile}
                    className="btn-primary"
                  >
                    {profileSaved ? (
                      <>
                        <Check size={18} />
                        已保存
                      </>
                    ) : (
                      <>
                        <Save size={18} />
                        保存修改
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
            
            {activeTab === 'password' && (
              <div className="card p-6">
                <h2 className="text-lg font-semibold mb-6">修改密码</h2>
                
                {passwordError && (
                  <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                    {passwordError}
                  </div>
                )}
                
                {passwordSuccess && (
                  <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
                    密码修改成功！
                  </div>
                )}
                
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-dark-300 mb-2">
                      当前密码
                    </label>
                    <input
                      type="password"
                      value={oldPassword}
                      onChange={(e) => setOldPassword(e.target.value)}
                      className="input"
                      placeholder="请输入当前密码"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-dark-300 mb-2">
                      新密码
                    </label>
                    <input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="input"
                      placeholder="请输入新密码（至少8位）"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-dark-300 mb-2">
                      确认新密码
                    </label>
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="input"
                      placeholder="请再次输入新密码"
                    />
                  </div>
                  
                  <button
                    onClick={handleChangePassword}
                    disabled={changePasswordMutation.isPending}
                    className="btn-primary"
                  >
                    {changePasswordMutation.isPending ? (
                      <>
                        <Loader2 size={18} className="animate-spin" />
                        修改中...
                      </>
                    ) : (
                      <>
                        <Lock size={18} />
                        修改密码
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
            
            {activeTab === 'notifications' && (
              <div className="card p-6">
                <h2 className="text-lg font-semibold mb-6">通知设置</h2>
                
                <div className="space-y-4">
                  <label className="flex items-center justify-between p-4 bg-dark-800/30 rounded-lg">
                    <div>
                      <p className="font-medium">审核通知</p>
                      <p className="text-sm text-dark-400">当您的贡献被审核时通知</p>
                    </div>
                    <input type="checkbox" defaultChecked className="w-5 h-5" />
                  </label>
                  
                  <label className="flex items-center justify-between p-4 bg-dark-800/30 rounded-lg">
                    <div>
                      <p className="font-medium">引用通知</p>
                      <p className="text-sm text-dark-400">当您的贡献被引用时通知</p>
                    </div>
                    <input type="checkbox" defaultChecked className="w-5 h-5" />
                  </label>
                  
                  <label className="flex items-center justify-between p-4 bg-dark-800/30 rounded-lg">
                    <div>
                      <p className="font-medium">任务通知</p>
                      <p className="text-sm text-dark-400">当有新任务分配给您时通知</p>
                    </div>
                    <input type="checkbox" defaultChecked className="w-5 h-5" />
                  </label>
                </div>
              </div>
            )}
            
            {activeTab === 'appearance' && (
              <div className="card p-6">
                <h2 className="text-lg font-semibold mb-6">外观设置</h2>
                
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-dark-300 mb-3">
                      主题
                    </label>
                    <div className="flex gap-4">
                      <button className="w-20 h-20 rounded-xl bg-dark-900 border-2 border-primary-500 flex flex-col items-center justify-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-dark-950" />
                        <span className="text-xs">深色</span>
                      </button>
                      <button className="w-20 h-20 rounded-xl bg-dark-800 border border-dark-600 flex flex-col items-center justify-center gap-2 opacity-50 cursor-not-allowed">
                        <div className="w-8 h-8 rounded-full bg-white" />
                        <span className="text-xs">浅色</span>
                      </button>
                      <button className="w-20 h-20 rounded-xl bg-dark-800 border border-dark-600 flex flex-col items-center justify-center gap-2 opacity-50 cursor-not-allowed">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-dark-950 to-white" />
                        <span className="text-xs">跟随系统</span>
                      </button>
                    </div>
                    <p className="text-xs text-dark-500 mt-2">更多主题即将推出</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

