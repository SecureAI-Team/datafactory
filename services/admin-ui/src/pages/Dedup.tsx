import { useState } from 'react'
import { Card, Tag, Button, Space, Modal, Typography, Spin, message, Tabs, Descriptions } from 'antd'
import { 
  MergeCellsOutlined, 
  EyeOutlined, 
  CheckOutlined,
  SwapOutlined,
  CloseOutlined
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dedupApi, DedupGroup, KUCandidate } from '../api'
import { useAuthStore } from '../store/authStore'

const { Title, Text, Paragraph } = Typography

function DedupGroupCard({ 
  group, 
  onApprove, 
  onDismiss,
  onViewDetails,
  isApproving,
  isDismissing 
}: { 
  group: DedupGroup
  onApprove: (groupId: string) => void
  onDismiss: (groupId: string) => void
  onViewDetails: (groupId: string) => void
  isApproving: boolean
  isDismissing: boolean
}) {
  return (
    <Card 
      size="small" 
      style={{ marginBottom: 16 }}
      title={
        <Space>
          <MergeCellsOutlined />
          <span>重复组 {group.group_id.substring(0, 8)}...</span>
          <Tag color="orange">相似度 {(group.similarity_score * 100).toFixed(0)}%</Tag>
          <Tag>{group.ku_ids.length} 个 KU</Tag>
        </Space>
      }
      extra={
        <Space>
          <Button 
            type="link" 
            icon={<EyeOutlined />}
            onClick={() => onViewDetails(group.group_id)}
          >
            查看详情
          </Button>
          <Button 
            type="primary" 
            icon={<CheckOutlined />}
            onClick={() => onApprove(group.group_id)}
            loading={isApproving}
          >
            批准合并
          </Button>
          <Button 
            icon={<CloseOutlined />}
            onClick={() => onDismiss(group.group_id)}
            loading={isDismissing}
          >
            非重复
          </Button>
        </Space>
      }
    >
      <div>
        <Text type="secondary">包含 KU IDs: </Text>
        {group.ku_ids.map((id) => (
          <Tag key={id} style={{ marginBottom: 4 }}>
            KU-{id}
          </Tag>
        ))}
      </div>
      <div style={{ marginTop: 8 }}>
        <Text type="secondary">创建时间: {new Date(group.created_at).toLocaleString()}</Text>
      </div>
    </Card>
  )
}

export default function Dedup() {
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [detailModal, setDetailModal] = useState<{ visible: boolean; groupId: string | null; data: { kus: KUCandidate[] } | null }>({
    visible: false,
    groupId: null,
    data: null,
  })
  const [loadingDetails, setLoadingDetails] = useState(false)

  // Fetch dedup groups
  const { data: groups, isLoading: loadingGroups } = useQuery({
    queryKey: ['dedup-groups', statusFilter],
    queryFn: () => dedupApi.getAll({ status: statusFilter === 'all' ? undefined : statusFilter, limit: 50 }),
  })

  // Fetch stats
  const { data: statsData, isLoading: loadingStats } = useQuery({
    queryKey: ['dedup-stats'],
    queryFn: () => dedupApi.getStats(),
  })

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: (groupId: string) => dedupApi.approve(groupId, user?.username || 'admin'),
    onSuccess: () => {
      message.success('已批准合并，将由系统自动执行')
      queryClient.invalidateQueries({ queryKey: ['dedup-groups'] })
      queryClient.invalidateQueries({ queryKey: ['dedup-stats'] })
    },
    onError: (error: Error) => message.error(`操作失败: ${error.message}`),
  })

  // Dismiss mutation
  const dismissMutation = useMutation({
    mutationFn: (groupId: string) => dedupApi.dismiss(groupId, user?.username || 'admin'),
    onSuccess: () => {
      message.success('已标记为非重复')
      queryClient.invalidateQueries({ queryKey: ['dedup-groups'] })
      queryClient.invalidateQueries({ queryKey: ['dedup-stats'] })
    },
    onError: (error: Error) => message.error(`操作失败: ${error.message}`),
  })

  const handleApprove = (groupId: string) => {
    Modal.confirm({
      title: '确认批准合并',
      content: '批准后，系统将自动执行合并操作。确定继续吗？',
      onOk: () => {
        approveMutation.mutate(groupId)
      },
    })
  }

  const handleDismiss = (groupId: string) => {
    Modal.confirm({
      title: '确认标记',
      content: '确定将此组标记为非重复吗？标记后这些 KU 将不再出现在去重列表中。',
      onOk: () => {
        dismissMutation.mutate(groupId)
      },
    })
  }

  const handleViewDetails = async (groupId: string) => {
    setLoadingDetails(true)
    setDetailModal({ visible: true, groupId, data: null })
    try {
      const details = await dedupApi.getGroupDetails(groupId)
      setDetailModal({ visible: true, groupId, data: details })
    } catch (error) {
      message.error('加载详情失败')
    } finally {
      setLoadingDetails(false)
    }
  }

  const pendingGroups = groups?.filter(g => g.status === 'pending') || []
  const approvedGroups = groups?.filter(g => g.status === 'approved') || []

  const tabItems = [
    {
      key: 'pending',
      label: `待处理 (${statsData?.pending ?? 0})`,
      children: (
        <Spin spinning={loadingGroups}>
          {pendingGroups.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
              <MergeCellsOutlined style={{ fontSize: 48, marginBottom: 16 }} />
              <p>暂无待处理的重复组</p>
            </div>
          ) : (
            pendingGroups.map(group => (
              <DedupGroupCard 
                key={group.group_id} 
                group={group}
                onApprove={handleApprove}
                onDismiss={handleDismiss}
                onViewDetails={handleViewDetails}
                isApproving={approveMutation.isPending}
                isDismissing={dismissMutation.isPending}
              />
            ))
          )}
        </Spin>
      ),
    },
    {
      key: 'approved',
      label: `待合并 (${statsData?.approved ?? 0})`,
      children: (
        <Spin spinning={loadingGroups}>
          {approvedGroups.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
              <CheckOutlined style={{ fontSize: 48, marginBottom: 16, color: '#f59e0b' }} />
              <p>暂无待合并的组</p>
            </div>
          ) : (
            approvedGroups.map(group => (
              <Card key={group.group_id} size="small" style={{ marginBottom: 8 }}>
                <Space>
                  <Tag color="orange">待合并</Tag>
                  <span>{group.group_id.substring(0, 8)}...</span>
                  <Text type="secondary">审核人: {group.reviewed_by}</Text>
                </Space>
              </Card>
            ))
          )}
        </Spin>
      ),
    },
    {
      key: 'merged',
      label: `已合并 (${statsData?.merged ?? 0})`,
      children: (
        <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
          <CheckOutlined style={{ fontSize: 48, marginBottom: 16, color: '#22c55e' }} />
          <p>已合并 {statsData?.merged ?? 0} 组记录</p>
        </div>
      ),
    },
    {
      key: 'dismissed',
      label: `非重复 (${statsData?.dismissed ?? 0})`,
      children: (
        <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
          <SwapOutlined style={{ fontSize: 48, marginBottom: 16 }} />
          <p>标记为非重复的记录: {statsData?.dismissed ?? 0} 组</p>
        </div>
      ),
    },
  ]

  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>去重工作台</Title>

      {/* Stats */}
      <Spin spinning={loadingStats}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16, marginBottom: 24 }}>
          <Card size="small">
            <Text type="secondary">总重复组</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>{statsData?.total ?? 0}</div>
          </Card>
          <Card size="small">
            <Text type="secondary">待处理</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#eab308' }}>{statsData?.pending ?? 0}</div>
          </Card>
          <Card size="small">
            <Text type="secondary">待合并</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#f59e0b' }}>{statsData?.approved ?? 0}</div>
          </Card>
          <Card size="small">
            <Text type="secondary">已合并</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#22c55e' }}>{statsData?.merged ?? 0}</div>
          </Card>
          <Card size="small">
            <Text type="secondary">非重复</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#64748b' }}>{statsData?.dismissed ?? 0}</div>
          </Card>
        </div>
      </Spin>

      {/* Main Content */}
      <Card>
        <Tabs 
          items={tabItems}
          activeKey={statusFilter}
          onChange={setStatusFilter}
        />
      </Card>

      {/* Help Text */}
      <div style={{ marginTop: 16, padding: 16, background: 'rgba(14, 165, 233, 0.1)', borderRadius: 8, border: '1px solid rgba(14, 165, 233, 0.3)' }}>
        <Text style={{ color: '#38bdf8' }}>
          💡 提示：系统会自动识别内容相似度高于 80% 的 KU 作为疑似重复。您可以批准合并（由系统自动执行），或标记为非重复。
        </Text>
      </div>

      {/* Detail Modal */}
      <Modal
        title={`重复组详情: ${detailModal.groupId?.substring(0, 8)}...`}
        open={detailModal.visible}
        onCancel={() => setDetailModal({ visible: false, groupId: null, data: null })}
        footer={null}
        width={800}
      >
        <Spin spinning={loadingDetails}>
          {detailModal.data?.kus && detailModal.data.kus.length > 0 ? (
            <div style={{ maxHeight: 500, overflowY: 'auto' }}>
              {detailModal.data.kus.map((ku, index) => (
                <Card 
                  key={ku.id} 
                  size="small" 
                  style={{ marginBottom: 12 }}
                  title={
                    <Space>
                      <Tag color={index === 0 ? 'blue' : 'default'}>KU-{ku.id}</Tag>
                      <span>{ku.title || '未命名'}</span>
                    </Space>
                  }
                >
                  <Descriptions size="small" column={2}>
                    <Descriptions.Item label="类型">{ku.ku_type || '-'}</Descriptions.Item>
                    <Descriptions.Item label="产品">{ku.product_id || '-'}</Descriptions.Item>
                    <Descriptions.Item label="版本">{ku.version}</Descriptions.Item>
                    <Descriptions.Item label="状态">
                      <Tag color={ku.status === 'published' ? 'green' : 'default'}>{ku.status}</Tag>
                    </Descriptions.Item>
                  </Descriptions>
                  {ku.summary && (
                    <div style={{ marginTop: 8, padding: 12, background: '#1e293b', borderRadius: 4 }}>
                      <Paragraph ellipsis={{ rows: 3 }} style={{ margin: 0, color: '#94a3b8' }}>
                        {ku.summary}
                      </Paragraph>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 24, color: '#64748b' }}>
              暂无详情数据
            </div>
          )}
        </Spin>
      </Modal>
    </div>
  )
}
