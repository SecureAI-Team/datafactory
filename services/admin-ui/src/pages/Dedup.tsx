import { useState } from 'react'
import { Card, Tag, Button, Space, Modal, Typography, Spin, message, Tabs, Descriptions, Input, InputNumber, Form } from 'antd'
import { 
  MergeCellsOutlined, 
  EyeOutlined, 
  CheckOutlined,
  SwapOutlined,
  CloseOutlined,
  PlusOutlined,
  SearchOutlined
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dedupApi, DedupGroup, KUCandidate, CreateDedupGroupRequest, SimilarKU } from '../api'
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
  const [createModal, setCreateModal] = useState(false)
  const [createForm] = Form.useForm()
  
  // Similar KU search state
  const [similarModal, setSimilarModal] = useState(false)
  const [searchKuId, setSearchKuId] = useState<string>('')
  const [similarKus, setSimilarKus] = useState<SimilarKU[]>([])
  const [loadingSimilar, setLoadingSimilar] = useState(false)
  const [selectedSimilarKus, setSelectedSimilarKus] = useState<string[]>([])

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

  // Create dedup group mutation
  const createMutation = useMutation({
    mutationFn: (data: CreateDedupGroupRequest) => dedupApi.create(data),
    onSuccess: () => {
      message.success('重复组已创建')
      queryClient.invalidateQueries({ queryKey: ['dedup-groups'] })
      queryClient.invalidateQueries({ queryKey: ['dedup-stats'] })
      setCreateModal(false)
      createForm.resetFields()
    },
    onError: (error: Error) => message.error(`创建失败: ${error.message}`),
  })

  // Execute merge mutation
  const mergeMutation = useMutation({
    mutationFn: ({ groupId, strategy }: { groupId: string; strategy: string }) => 
      dedupApi.executeMerge(groupId, strategy),
    onSuccess: (data) => {
      message.success(`合并成功！新 KU ID: ${data.merged_ku_id}`)
      queryClient.invalidateQueries({ queryKey: ['dedup-groups'] })
      queryClient.invalidateQueries({ queryKey: ['dedup-stats'] })
    },
    onError: (error: Error) => message.error(`合并失败: ${error.message}`),
  })

  const handleExecuteMerge = (groupId: string) => {
    Modal.confirm({
      title: '执行合并',
      content: '确定要立即执行合并操作吗？合并后原 KU 将被标记为已合并。',
      okText: '确认合并',
      cancelText: '取消',
      onOk: () => {
        mergeMutation.mutate({ groupId, strategy: 'comprehensive' })
      },
    })
  }

  // Search similar KUs handler
  const handleSearchSimilar = async () => {
    if (!searchKuId.trim()) {
      message.warning('请输入 KU ID')
      return
    }
    
    const kuId = parseInt(searchKuId.trim(), 10)
    if (isNaN(kuId)) {
      message.error('请输入有效的数字 ID')
      return
    }
    
    setLoadingSimilar(true)
    setSimilarKus([])
    setSelectedSimilarKus([])
    
    try {
      const results = await dedupApi.findSimilar(kuId, { min_similarity: 0.3, limit: 20 })
      setSimilarKus(results)
      if (results.length === 0) {
        message.info('未找到相似的 KU')
      }
    } catch (error: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const axiosError = error as any
      if (axiosError?.response?.status === 404) {
        message.error(`KU ID ${kuId} 不存在，请输入有效的 KU ID`)
      } else if (axiosError?.response?.status === 400) {
        message.error(axiosError?.response?.data?.detail || '该 KU 无法进行相似搜索')
      } else {
        message.error(`搜索失败: ${axiosError?.message || '未知错误'}`)
      }
    } finally {
      setLoadingSimilar(false)
    }
  }

  // Create dedup group from similar search results
  const handleCreateFromSimilar = () => {
    if (selectedSimilarKus.length === 0) {
      message.warning('请至少选择一个相似 KU')
      return
    }
    
    const allKuIds = [searchKuId, ...selectedSimilarKus]
    
    if (allKuIds.length < 2) {
      message.warning('至少需要 2 个 KU 才能创建重复组')
      return
    }
    
    createMutation.mutate({
      ku_ids: allKuIds,
      similarity_score: 0.8,
      creator: user?.username || 'admin',
    })
    
    // Reset and close
    setSimilarModal(false)
    setSearchKuId('')
    setSimilarKus([])
    setSelectedSimilarKus([])
  }

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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Space>
                    <Tag color="orange">待合并</Tag>
                    <span>{group.group_id.substring(0, 8)}...</span>
                    <Tag>{group.ku_ids.length} 个 KU</Tag>
                    <Text type="secondary">审核人: {group.reviewed_by}</Text>
                  </Space>
                  <Space>
                    <Button 
                      type="link" 
                      icon={<EyeOutlined />}
                      onClick={() => handleViewDetails(group.group_id)}
                    >
                      查看
                    </Button>
                    <Button 
                      type="primary"
                      icon={<MergeCellsOutlined />}
                      onClick={() => handleExecuteMerge(group.group_id)}
                      loading={mergeMutation.isPending}
                    >
                      执行合并
                    </Button>
                  </Space>
                </div>
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={2} style={{ margin: 0 }}>去重工作台</Title>
        <Space>
          <Button 
            icon={<SearchOutlined />}
            onClick={() => setSimilarModal(true)}
          >
            查找相似 KU
          </Button>
          <Button 
            type="primary" 
            icon={<PlusOutlined />}
            onClick={() => setCreateModal(true)}
          >
            手动添加重复组
          </Button>
        </Space>
      </div>

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

      {/* Create Dedup Group Modal */}
      <Modal
        title="手动添加重复组"
        open={createModal}
        onCancel={() => {
          setCreateModal(false)
          createForm.resetFields()
        }}
        onOk={() => {
          createForm.validateFields().then((values) => {
            // Parse KU IDs from comma-separated string
            const kuIds = values.ku_ids
              .split(/[,，\s]+/)
              .map((id: string) => id.trim())
              .filter((id: string) => id.length > 0)
            
            if (kuIds.length < 2) {
              message.error('至少需要 2 个 KU ID')
              return
            }
            
            createMutation.mutate({
              ku_ids: kuIds,
              similarity_score: values.similarity_score || 0.8,
              creator: user?.username || 'admin',
            })
          })
        }}
        confirmLoading={createMutation.isPending}
        width={500}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item 
            label="KU IDs" 
            name="ku_ids"
            rules={[{ required: true, message: '请输入至少 2 个 KU ID' }]}
            extra="输入多个 KU ID，用逗号或空格分隔"
          >
            <Input.TextArea 
              rows={3} 
              placeholder="例如: 1, 2, 3 或 1 2 3" 
            />
          </Form.Item>
          
          <Form.Item 
            label="相似度分数" 
            name="similarity_score"
            initialValue={0.8}
            extra="手动添加的组可设置一个估计的相似度分数"
          >
            <InputNumber 
              min={0} 
              max={1} 
              step={0.05} 
              style={{ width: '100%' }}
            />
          </Form.Item>
        </Form>
        
        <div style={{ marginTop: 16, padding: 12, background: 'rgba(251, 191, 36, 0.1)', borderRadius: 8, border: '1px solid rgba(251, 191, 36, 0.3)' }}>
          <Text style={{ color: '#fbbf24', fontSize: 12 }}>
            ⚠️ 提示：请确保输入的 KU ID 确实存在且内容相似。添加后需要在"待处理"列表中批准合并。
          </Text>
        </div>
      </Modal>

      {/* Similar KU Search Modal */}
      <Modal
        title="查找相似 KU"
        open={similarModal}
        onCancel={() => {
          setSimilarModal(false)
          setSearchKuId('')
          setSimilarKus([])
          setSelectedSimilarKus([])
        }}
        footer={
          <Space>
            <Button onClick={() => setSimilarModal(false)}>取消</Button>
            <Button 
              type="primary" 
              onClick={handleCreateFromSimilar}
              disabled={selectedSimilarKus.length === 0}
              loading={createMutation.isPending}
            >
              创建重复组 ({selectedSimilarKus.length + (searchKuId ? 1 : 0)} 个 KU)
            </Button>
          </Space>
        }
        width={700}
      >
        <div style={{ marginBottom: 16 }}>
          <Space.Compact style={{ width: '100%' }}>
            <Input
              placeholder="输入 KU ID"
              value={searchKuId}
              onChange={(e) => setSearchKuId(e.target.value)}
              onPressEnter={handleSearchSimilar}
              style={{ width: 'calc(100% - 100px)' }}
            />
            <Button 
              type="primary" 
              icon={<SearchOutlined />}
              onClick={handleSearchSimilar}
              loading={loadingSimilar}
            >
              搜索
            </Button>
          </Space.Compact>
          <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
            输入一个 KU ID，系统将查找与其内容相似的其他 KU
          </Text>
        </div>

        <Spin spinning={loadingSimilar}>
          {similarKus.length > 0 ? (
            <div style={{ maxHeight: 400, overflowY: 'auto' }}>
              {similarKus.map((ku) => (
                <Card 
                  key={ku.id} 
                  size="small" 
                  style={{ 
                    marginBottom: 8,
                    cursor: 'pointer',
                    border: selectedSimilarKus.includes(ku.id) 
                      ? '2px solid #3b82f6' 
                      : '1px solid #334155'
                  }}
                  onClick={() => {
                    if (selectedSimilarKus.includes(ku.id)) {
                      setSelectedSimilarKus(prev => prev.filter(id => id !== ku.id))
                    } else {
                      setSelectedSimilarKus(prev => [...prev, ku.id])
                    }
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <Space>
                        <Tag color="blue">KU-{ku.id}</Tag>
                        <Text strong>{ku.title || '未命名'}</Text>
                      </Space>
                      <div style={{ marginTop: 4 }}>
                        <Tag>{ku.ku_type || '未分类'}</Tag>
                        {ku.product_id && <Tag color="cyan">{ku.product_id}</Tag>}
                      </div>
                      {ku.summary && (
                        <Paragraph 
                          ellipsis={{ rows: 2 }} 
                          style={{ margin: '8px 0 0 0', color: '#94a3b8', fontSize: 12 }}
                        >
                          {ku.summary}
                        </Paragraph>
                      )}
                    </div>
                    <Tag color={ku.similarity_score >= 0.7 ? 'red' : ku.similarity_score >= 0.5 ? 'orange' : 'default'}>
                      相似度 {(ku.similarity_score * 100).toFixed(0)}%
                    </Tag>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
              <SearchOutlined style={{ fontSize: 32, marginBottom: 16 }} />
              <p>输入 KU ID 并点击搜索以查找相似内容</p>
            </div>
          )}
        </Spin>
      </Modal>
    </div>
  )
}
