import { Card, Row, Col, Statistic, Table, Tag, List, Typography, Spin, message } from 'antd'
import {
  FileTextOutlined,
  DatabaseOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { statsApi, reviewApi } from '../api'

const { Title, Text } = Typography

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
  
  // Handle errors
  if (overviewError) {
    message.error('加载统计数据失败')
  }
  
  const isLoading = loadingOverview || loadingActivity || loadingReviews
  
  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>仪表盘</Title>
      
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
    </div>
  )
}
