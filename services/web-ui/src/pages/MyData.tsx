import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Upload,
  FileText,
  CheckCircle,
  Clock,
  XCircle,
  Award,
  TrendingUp,
  BookOpen,
  Star,
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import apiClient from '../api/client'
import clsx from 'clsx'

interface ContributionStats {
  total_contributions: number
  approved_count: number
  rejected_count: number
  pending_count: number
  citation_count: number
  achievements: string[]
  streak_days: number
}

const achievements = [
  { id: 'case_master', icon: '📋', name: '案例达人', desc: '贡献5个案例', unlocked: true },
  { id: 'talk_expert', icon: '💬', name: '话术专家', desc: '贡献10条话术', unlocked: true },
  { id: 'pioneer', icon: '🚀', name: '知识先锋', desc: '首批贡献者', unlocked: true },
  { id: 'high_cite', icon: '📚', name: '高频引用', desc: '被引用50次', unlocked: false },
  { id: 'streak_7', icon: '🔥', name: '连续贡献', desc: '连续贡献7天', unlocked: false },
  { id: 'quality', icon: '⭐', name: '质量之星', desc: '通过率100%', unlocked: false },
]

const mockContributions = [
  {
    id: 1,
    title: '华为PCB产线案例.pdf',
    type: 'file_upload',
    ku_type: '客户案例',
    product: 'AOI8000',
    status: 'approved',
    citation_count: 23,
    created_at: '2024-01-15',
  },
  {
    id: 2,
    title: '比亚迪电池检测方案.docx',
    type: 'file_upload',
    ku_type: '方案书',
    product: 'AOI8000',
    status: 'pending',
    citation_count: 0,
    created_at: '2024-01-20',
  },
  {
    id: 3,
    title: '某客户报价单.xlsx',
    type: 'file_upload',
    ku_type: '报价单',
    product: 'AOI5000',
    status: 'rejected',
    citation_count: 0,
    created_at: '2024-01-18',
    review_comment: '包含敏感价格信息，请脱敏后重新提交',
  },
]

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType
  label: string
  value: number | string
  color: string
}) {
  return (
    <div className="card p-6">
      <div className="flex items-center gap-4">
        <div
          className={clsx(
            'w-12 h-12 rounded-xl flex items-center justify-center',
            color === 'primary' && 'bg-primary-500/20 text-primary-400',
            color === 'green' && 'bg-green-500/20 text-green-400',
            color === 'yellow' && 'bg-yellow-500/20 text-yellow-400',
            color === 'purple' && 'bg-purple-500/20 text-purple-400'
          )}
        >
          <Icon size={24} />
        </div>
        <div>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-sm text-dark-400">{label}</p>
        </div>
      </div>
    </div>
  )
}

export default function MyData() {
  const [activeTab, setActiveTab] = useState<'contributions' | 'achievements'>('contributions')
  const { user } = useAuthStore()
  
  // Fetch user stats
  const { data: stats } = useQuery<ContributionStats>({
    queryKey: ['user-stats', user?.id],
    queryFn: async () => {
      const response = await apiClient.get(`/api/users/${user?.id}/stats`)
      return response.data
    },
    enabled: !!user?.id,
  })
  
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">我的资料</h1>
            <p className="text-dark-400 mt-1">查看您的贡献和成就</p>
          </div>
          <button className="btn-primary">
            <Upload size={18} />
            上传材料
          </button>
        </div>
        
        {/* Stats Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={Upload}
            label="总贡献"
            value={stats?.total_contributions || 15}
            color="primary"
          />
          <StatCard
            icon={CheckCircle}
            label="已入库"
            value={stats?.approved_count || 12}
            color="green"
          />
          <StatCard
            icon={Clock}
            label="审核中"
            value={stats?.pending_count || 2}
            color="yellow"
          />
          <StatCard
            icon={BookOpen}
            label="被引用"
            value={stats?.citation_count || 89}
            color="purple"
          />
        </div>
        
        {/* Tabs */}
        <div className="flex gap-4 mb-6">
          <button
            onClick={() => setActiveTab('contributions')}
            className={clsx(
              'px-4 py-2 rounded-lg font-medium transition-all',
              activeTab === 'contributions'
                ? 'bg-primary-500/20 text-primary-400'
                : 'text-dark-400 hover:text-dark-200'
            )}
          >
            <FileText size={18} className="inline mr-2" />
            贡献记录
          </button>
          <button
            onClick={() => setActiveTab('achievements')}
            className={clsx(
              'px-4 py-2 rounded-lg font-medium transition-all',
              activeTab === 'achievements'
                ? 'bg-primary-500/20 text-primary-400'
                : 'text-dark-400 hover:text-dark-200'
            )}
          >
            <Award size={18} className="inline mr-2" />
            成就徽章
          </button>
        </div>
        
        {/* Content */}
        {activeTab === 'contributions' ? (
          <div className="space-y-4">
            {mockContributions.map((contribution) => (
              <div key={contribution.id} className="card p-4 flex items-center gap-4">
                {/* Status Icon */}
                <div
                  className={clsx(
                    'w-10 h-10 rounded-lg flex items-center justify-center',
                    contribution.status === 'approved' && 'bg-green-500/20',
                    contribution.status === 'pending' && 'bg-yellow-500/20',
                    contribution.status === 'rejected' && 'bg-red-500/20'
                  )}
                >
                  {contribution.status === 'approved' && (
                    <CheckCircle className="text-green-400" size={20} />
                  )}
                  {contribution.status === 'pending' && (
                    <Clock className="text-yellow-400" size={20} />
                  )}
                  {contribution.status === 'rejected' && (
                    <XCircle className="text-red-400" size={20} />
                  )}
                </div>
                
                {/* Info */}
                <div className="flex-1">
                  <h3 className="font-medium">{contribution.title}</h3>
                  <p className="text-sm text-dark-400">
                    类型: {contribution.ku_type} | 产品: {contribution.product} |{' '}
                    {contribution.status === 'approved'
                      ? `入库于 ${contribution.created_at}`
                      : contribution.status === 'pending'
                      ? `提交于 ${contribution.created_at}`
                      : `提交于 ${contribution.created_at}`}
                  </p>
                  {contribution.review_comment && (
                    <p className="text-sm text-red-400 mt-1">
                      审核意见: {contribution.review_comment}
                    </p>
                  )}
                </div>
                
                {/* Citation Count */}
                {contribution.status === 'approved' && contribution.citation_count > 0 && (
                  <div className="text-right">
                    <p className="text-lg font-bold text-primary-400">
                      {contribution.citation_count}
                    </p>
                    <p className="text-xs text-dark-400">被引用</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {achievements.map((achievement) => (
              <div
                key={achievement.id}
                className={clsx(
                  'card p-6 text-center',
                  !achievement.unlocked && 'opacity-50'
                )}
              >
                <div className="text-4xl mb-3">{achievement.icon}</div>
                <h3 className="font-medium mb-1">{achievement.name}</h3>
                <p className="text-sm text-dark-400">{achievement.desc}</p>
                {achievement.unlocked ? (
                  <span className="inline-block mt-3 text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded">
                    ✓ 已获得
                  </span>
                ) : (
                  <span className="inline-block mt-3 text-xs bg-dark-700 text-dark-400 px-2 py-1 rounded">
                    🔒 未解锁
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

