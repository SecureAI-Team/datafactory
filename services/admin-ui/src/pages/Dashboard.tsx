import { useState } from 'react'
import { Card, Row, Col, Statistic, Table, Tag, List, Typography, Spin, message, Button, Modal, Select, Space } from 'antd'
import {
  FileTextOutlined,
  DatabaseOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  RiseOutlined,
  PlayCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { statsApi, reviewApi } from '../api'

const { Title, Text } = Typography

// Simple Bar Chart Component
function SimpleBarChart({ data }: { data: { label: string; value: number }[] }) {
  const maxValue = Math.max(...data.map(d => d.value), 1)
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 120, paddingTop: 16 }}>
      {data.map((item, index) => (
        <div key={index} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div 
            style={{ 
              width: '100%', 
              height: `${(item.value / maxValue) * 100}px`,
              backgroundColor: '#0ea5e9',
              borderRadius: '4px 4px 0 0',
              transition: 'height 0.3s ease',
              minHeight: 4
            }} 
          />
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4 }}>{item.label}</Text>
          <Text style={{ fontSize: 12 }}>{item.value}</Text>
        </div>
      ))}
    </div>
  )
}

// Simple Pie Chart using Progress circles
function KUDistributionChart({ data }: { data: { name: string; value: number; color: string }[] }) {
  const total = data.reduce((sum, d) => sum + d.value, 0) || 1
  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        {data.map((item, index) => (
          <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 8, width: '48%' }}>
            <div style={{ width: 12, height: 12, borderRadius: 2, backgroundColor: item.color }} />
            <Text style={{ fontSize: 12, flex: 1 }}>{item.name}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>{Math.round((item.value / total) * 100)}%</Text>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 16, display: 'flex', height: 16, borderRadius: 4, overflow: 'hidden' }}>
        {data.map((item, index) => (
          <div 
            key={index}
            style={{ 
              width: `${(item.value / total) * 100}%`,
              backgroundColor: item.color,
              minWidth: item.value > 0 ? 4 : 0
            }}
            title={`${item.name}: ${item.value}`}
          />
        ))}
      </div>
    </div>
  )
}

const columns = [
  { title: '标题', dataIndex: 'title', key: 'title' },
  { title: '贡献者', dataIndex: 'contributor_name', key: 'contributor_name' },
  { 
    title: '类型', 
    dataIndex: 'contribution_type', 
    key: 'contribution_type', 
    render: (type: string) => {
      const typeLabels: Record<string, string> = {
        'file_upload': '文件上传',
        'draft_ku': '草稿 KU',
        'signal': '现场信号',
        'feedback': '反馈',
        'correction': '修正',
      }
      return <Tag>{typeLabels[type] || type}</Tag>
    }
  },
  { title: '提交时间', dataIndex: 'created_at', key: 'created_at' },
]

function formatTimeAgo(isoString: string | null | undefined): string {
  if (!isoString) return '未知时间'
  
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  
  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins}分钟前`
  
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}小时前`
  
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}天前`
}

export default function Dashboard() {
  const queryClient = useQueryClient()
  const [pipelineModalVisible, setPipelineModalVisible] = useState(false)
  const [selectedDag, setSelectedDag] = useState('ingest_to_bronze')
  const [reindexing, setReindexing] = useState(false)
  
  // Fetch overview stats
  const { data: overview, isLoading: loadingOverview, error: overviewError } = useQuery({
    queryKey: ['stats-overview'],
    queryFn: () => statsApi.getOverview(),
    staleTime: 30000,
  })
  
  // Fetch recent activity
  const { data: activityData, isLoading: loadingActivity } = useQuery({
    queryKey: ['stats-activity'],
    queryFn: () => statsApi.getRecentActivity(10),
    staleTime: 30000,
  })
  
  // Fetch pending reviews
  const { data: reviewQueue, isLoading: loadingReviews } = useQuery({
    queryKey: ['review-queue-preview'],
    queryFn: () => reviewApi.getQueue({ status_filter: 'pending', limit: 5 }),
    staleTime: 30000,
  })
  
  // Fetch pipeline stats (real API)
  const { data: pipelineData } = useQuery({
    queryKey: ['stats-pipeline'],
    queryFn: () => statsApi.getPipeline(7),
    staleTime: 60000,
  })
  
  // Transform pipeline data for chart
  const pipelineTrends = {
    trends: Object.entries(pipelineData?.daily_stats || {})
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-7)
      .map(([date, stats]) => {
        const typedStats = stats as { success: number; failed: number; running: number }
        return {
          label: new Date(date).toLocaleDateString('zh-CN', { weekday: 'short' }),
          value: typedStats.success + typedStats.failed + typedStats.running
        }
      })
  }
  
  // Fetch quality stats for KU distribution (real API)
  const { data: qualityData } = useQuery({
    queryKey: ['stats-quality-dashboard'],
    queryFn: () => statsApi.getQuality(),
    staleTime: 60000,
  })
  
  // Transform KU distribution data for chart
  const categoryColors: Record<string, string> = {
    'core': '#0ea5e9',
    'case': '#22c55e',
    'solution': '#8b5cf6',
    'quote': '#f59e0b',
    'sales': '#ec4899',
    'delivery': '#06b6d4',
    'field': '#84cc16',
  }
  
  const kuDistribution = {
    distribution: Object.entries(qualityData?.ku_type_distribution || {}).map(([type, count]) => {
      const category = type.split('.')[0] || 'other'
      return {
        name: type,
        value: count as number,
        color: categoryColors[category] || '#64748b'
      }
    })
  }
  
  // Fetch available DAGs
  const { data: dagsData } = useQuery({
    queryKey: ['available-dags'],
    queryFn: () => statsApi.getAvailableDags(),
    staleTime: 300000, // 5 minutes
  })
  
  // Trigger pipeline mutation
  const triggerMutation = useMutation({
    mutationFn: (dagId: string) => statsApi.triggerPipeline(dagId),
    onSuccess: (result) => {
      if (result.success) {
        message.success(result.message)
        setPipelineModalVisible(false)
        queryClient.invalidateQueries({ queryKey: ['stats-pipeline'] })
        queryClient.invalidateQueries({ queryKey: ['stats-activity'] })
      } else {
        message.error(result.message)
      }
    },
    onError: () => {
      message.error('触发 Pipeline 失败')
    },
  })

  // Reindex all KUs mutation
  const reindexMutation = useMutation({
    mutationFn: () => reviewApi.reindexAll(),
    onSuccess: (result) => {
      message.success(`重建索引完成: 成功 ${result.indexed} 个, 失败 ${result.failed} 个`)
      setReindexing(false)
      queryClient.invalidateQueries({ queryKey: ['stats-overview'] })
    },
    onError: () => {
      message.error('重建索引失败')
      setReindexing(false)
    },
  })

  const handleReindex = () => {
    Modal.confirm({
      title: '重建 OpenSearch 索引',
      content: '这将重新索引所有已审批的贡献到 OpenSearch，确保它们可被检索。此操作可能需要一些时间。',
      okText: '确认重建',
      cancelText: '取消',
      onOk: () => {
        setReindexing(true)
        reindexMutation.mutate()
      },
    })
  }
  
  // Handle errors
  if (overviewError) {
    message.error('加载统计数据失败')
  }
  
  const _isLoading = loadingOverview || loadingActivity || loadingReviews
  void _isLoading // suppress unused warning
  
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={2} style={{ marginBottom: 0 }}>仪表盘</Title>
        <Space>
          <Button
            icon={<SyncOutlined spin={reindexing} />}
            onClick={handleReindex}
            loading={reindexing}
          >
            重建索引
          </Button>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={() => setPipelineModalVisible(true)}
          >
            处理新材料
          </Button>
        </Space>
      </div>
      
      {/* Stats Cards */}
      <Spin spinning={loadingOverview}>
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="今日处理"
                value={overview?.today_processed ?? 0}
                prefix={<FileTextOutlined />}
                valueStyle={{ color: '#0ea5e9' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="KU 总量"
                value={overview?.total_kus ?? 0}
                prefix={<DatabaseOutlined />}
                valueStyle={{ color: '#22c55e' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="待审核"
                value={overview?.pending_reviews ?? 0}
                prefix={<ClockCircleOutlined />}
                valueStyle={{ color: '#eab308' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="失败任务"
                value={overview?.failed_runs ?? 0}
                prefix={<WarningOutlined />}
                valueStyle={{ color: '#ef4444' }}
              />
            </Card>
          </Col>
        </Row>
      </Spin>
      
      {/* Charts Row */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={16}>
          {/* Pipeline Trend Chart */}
          <Card 
            title={
              <span>
                <RiseOutlined style={{ marginRight: 8 }} />
                Pipeline 处理趋势（近7天）
              </span>
            }
          >
            <SimpleBarChart data={pipelineTrends?.trends ?? []} />
          </Card>
        </Col>
        
        <Col span={8}>
          {/* KU Distribution Chart */}
          <Card title="KU 类型分布">
            <KUDistributionChart data={kuDistribution?.distribution ?? []} />
            <div style={{ marginTop: 16, textAlign: 'center' }}>
              <Text type="secondary">
                总计: {(kuDistribution?.distribution ?? []).reduce((sum, d) => sum + d.value, 0)} 个 KU
              </Text>
            </div>
          </Card>
        </Col>
      </Row>
      
      {/* Main Content */}
      <Row gutter={[16, 16]}>
        <Col span={16}>
          {/* Pending Reviews */}
          <Card 
            title="待审核队列" 
            extra={<a href="/review">查看全部</a>}
            style={{ marginBottom: 16 }}
          >
            <Spin spinning={loadingReviews}>
              <Table 
                dataSource={reviewQueue?.contributions ?? []} 
                columns={columns} 
                rowKey="id"
                pagination={false}
                size="small"
                locale={{ emptyText: '暂无待审核项' }}
              />
            </Spin>
          </Card>
        </Col>
        
        <Col span={8}>
          {/* Recent Activity */}
          <Card title="最近活动">
            <Spin spinning={loadingActivity}>
              <List
                dataSource={activityData?.activities ?? []}
                locale={{ emptyText: '暂无活动记录' }}
                renderItem={(item) => (
                  <List.Item style={{ padding: '8px 0' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      {item.status === 'success' && <CheckCircleOutlined style={{ color: '#22c55e' }} />}
                      {item.status === 'running' && <SyncOutlined spin style={{ color: '#0ea5e9' }} />}
                      {(item.status === 'failed' || item.status === 'error') && <WarningOutlined style={{ color: '#ef4444' }} />}
                      {!['success', 'running', 'failed', 'error'].includes(item.status) && <SyncOutlined style={{ color: '#0ea5e9' }} />}
                      <div>
                        <Text style={{ fontSize: 13 }}>{item.message}</Text>
                        <br />
                        <Text type="secondary" style={{ fontSize: 11 }}>{formatTimeAgo(item.time)}</Text>
                      </div>
                    </div>
                  </List.Item>
                )}
              />
            </Spin>
          </Card>
        </Col>
      </Row>
      
      {/* Pipeline Trigger Modal */}
      <Modal
        title={
          <span>
            <PlayCircleOutlined style={{ marginRight: 8 }} />
            触发 Pipeline
          </span>
        }
        open={pipelineModalVisible}
        onCancel={() => setPipelineModalVisible(false)}
        onOk={() => triggerMutation.mutate(selectedDag)}
        okText="触发"
        okButtonProps={{ loading: triggerMutation.isPending }}
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">选择要触发的 Pipeline：</Text>
        </div>
        <Select
          style={{ width: '100%' }}
          value={selectedDag}
          onChange={setSelectedDag}
          options={(dagsData?.dags ?? []).map(dag => ({
            value: dag.id,
            label: (
              <div>
                <div style={{ fontWeight: 500 }}>{dag.name}</div>
                <div style={{ fontSize: 12, color: '#94a3b8' }}>{dag.description}</div>
              </div>
            ),
          }))}
          optionLabelProp="label"
        />
        <div style={{ marginTop: 16, padding: 12, background: '#1e293b', borderRadius: 8 }}>
          <Space direction="vertical" size={4}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ThunderboltOutlined style={{ marginRight: 4 }} />
              提示：触发后，Pipeline 将在后台处理新上传的材料
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              处理流程：导入 → 提取 → 扩展 → 索引 → 发布
            </Text>
          </Space>
        </div>
      </Modal>
    </div>
  )
}
