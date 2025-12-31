import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Upload,
  FileText,
  CheckCircle,
  Clock,
  XCircle,
  Award,
  BookOpen,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { contributeApi, Contribution, ContributionStats } from '../api/contribute'
import clsx from 'clsx'

// Achievement definitions - these could come from API in future
const achievementDefinitions = [
  { id: 'case_master', icon: '📋', name: '案例达人', desc: '贡献5个案例' },
  { id: 'talk_expert', icon: '💬', name: '话术专家', desc: '贡献10条话术' },
  { id: 'pioneer', icon: '🚀', name: '知识先锋', desc: '首批贡献者' },
  { id: 'high_cite', icon: '📚', name: '高频引用', desc: '被引用50次' },
  { id: 'streak_7', icon: '🔥', name: '连续贡献', desc: '连续贡献7天' },
  { id: 'quality', icon: '⭐', name: '质量之星', desc: '通过率100%' },
]

function StatCard({
  icon: Icon,
  label,
  value,
  color,
  loading,
}: {
  icon: React.ElementType
  label: string
  value: number | string
  color: string
  loading?: boolean
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
          {loading ? (
            <div className="animate-pulse">
              <div className="h-6 w-12 bg-dark-700 rounded mb-1"></div>
              <div className="h-4 w-16 bg-dark-700 rounded"></div>
            </div>
          ) : (
            <>
              <p className="text-2xl font-bold">{value}</p>
              <p className="text-sm text-dark-400">{label}</p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function ContributionItem({ contribution }: { contribution: Contribution }) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved':
        return 'bg-green-500/20'
      case 'pending':
        return 'bg-yellow-500/20'
      case 'rejected':
        return 'bg-red-500/20'
      default:
        return 'bg-dark-700'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'approved':
        return <CheckCircle className="text-green-400" size={20} />
      case 'pending':
        return <Clock className="text-yellow-400" size={20} />
      case 'rejected':
        return <XCircle className="text-red-400" size={20} />
      default:
        return <AlertCircle className="text-dark-400" size={20} />
    }
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('zh-CN')
    } catch {
      return dateString
    }
  }

  const getKUTypeName = (code: string | undefined) => {
    const types: Record<string, string> = {
      'product_spec': '产品规格',
      'case_study': '客户案例',
      'solution': '方案书',
      'quote': '报价单',
      'talk_track': '话术',
      'faq': '常见问答',
    }
    return code ? types[code] || code : '未分类'
  }

  return (
    <div className="card p-4 flex items-center gap-4">
      {/* Status Icon */}
      <div
        className={clsx(
          'w-10 h-10 rounded-lg flex items-center justify-center',
          getStatusColor(contribution.status)
        )}
      >
        {getStatusIcon(contribution.status)}
      </div>

      {/* Info */}
      <div className="flex-1">
        <h3 className="font-medium">{contribution.title || contribution.file_name || '未命名贡献'}</h3>
        <p className="text-sm text-dark-400">
          类型: {getKUTypeName(contribution.ku_type_code)} | 
          产品: {contribution.product_id || '未关联'} |{' '}
          {contribution.status === 'approved'
            ? `入库于 ${formatDate(contribution.reviewed_at || contribution.updated_at || contribution.created_at)}`
            : `提交于 ${formatDate(contribution.created_at)}`}
        </p>
        {contribution.review_comment && contribution.status === 'rejected' && (
          <p className="text-sm text-red-400 mt-1">
            审核意见: {contribution.review_comment}
          </p>
        )}
      </div>

      {/* Citation Count - Note: citation_count may need to come from a different endpoint */}
      {contribution.status === 'approved' && (
        <div className="text-right">
          <p className="text-lg font-bold text-primary-400">-</p>
          <p className="text-xs text-dark-400">引用待统计</p>
        </div>
      )}
    </div>
  )
}

export default function MyData() {
  const [activeTab, setActiveTab] = useState<'contributions' | 'achievements'>('contributions')
  const { user } = useAuthStore()

  // Fetch contribution stats
  const { 
    data: stats, 
    isLoading: statsLoading,
    error: statsError 
  } = useQuery<ContributionStats>({
    queryKey: ['contribution-stats'],
    queryFn: contributeApi.getStats,
    enabled: !!user,
    staleTime: 30000, // Cache for 30 seconds
  })

  // Fetch user contributions
  const {
    data: contributionsData,
    isLoading: contributionsLoading,
    error: contributionsError,
  } = useQuery({
    queryKey: ['my-contributions'],
    queryFn: () => contributeApi.getMine({ limit: 50 }),
    enabled: !!user,
    staleTime: 30000,
  })

  const contributions = contributionsData?.contributions || []

  // Compute which achievements are unlocked based on stats
  const unlockedAchievements = new Set<string>()
  if (stats) {
    if (stats.achievements) {
      stats.achievements.forEach(a => unlockedAchievements.add(a))
    }
    // Also check based on stats
    if (stats.total_contributions >= 1) unlockedAchievements.add('pioneer')
    if (stats.approved_count >= 5) unlockedAchievements.add('case_master')
    if (stats.approved_count >= 10) unlockedAchievements.add('talk_expert')
    if (stats.citation_count >= 50) unlockedAchievements.add('high_cite')
    if (stats.streak_days >= 7) unlockedAchievements.add('streak_7')
    if (stats.total_contributions > 0 && stats.approved_count === stats.total_contributions) {
      unlockedAchievements.add('quality')
    }
  }

  const achievementsWithStatus = achievementDefinitions.map(a => ({
    ...a,
    unlocked: unlockedAchievements.has(a.id),
  }))

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

        {/* Error Display */}
        {statsError && (
          <div className="mb-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
            <AlertCircle className="inline mr-2" size={18} />
            统计数据加载失败，请稍后重试
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={Upload}
            label="总贡献"
            value={stats?.total_contributions ?? 0}
            color="primary"
            loading={statsLoading}
          />
          <StatCard
            icon={CheckCircle}
            label="已入库"
            value={stats?.approved_count ?? 0}
            color="green"
            loading={statsLoading}
          />
          <StatCard
            icon={Clock}
            label="审核中"
            value={stats?.pending_count ?? 0}
            color="yellow"
            loading={statsLoading}
          />
          <StatCard
            icon={BookOpen}
            label="被引用"
            value={stats?.citation_count ?? 0}
            color="purple"
            loading={statsLoading}
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
            {contributionsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="animate-spin text-primary-400" size={32} />
              </div>
            ) : contributionsError ? (
              <div className="p-8 text-center text-dark-400">
                <AlertCircle className="mx-auto mb-2" size={32} />
                <p>加载贡献记录失败，请稍后重试</p>
              </div>
            ) : contributions.length === 0 ? (
              <div className="p-8 text-center text-dark-400">
                <FileText className="mx-auto mb-2 opacity-50" size={48} />
                <p className="mb-4">您还没有贡献任何资料</p>
                <button className="btn-primary">
                  <Upload size={18} />
                  上传第一份资料
                </button>
              </div>
            ) : (
              contributions.map((contribution) => (
                <ContributionItem key={contribution.id} contribution={contribution} />
              ))
            )}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {achievementsWithStatus.map((achievement) => (
              <div
                key={achievement.id}
                className={clsx(
                  'card p-6 text-center transition-all',
                  !achievement.unlocked && 'opacity-50 grayscale'
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
