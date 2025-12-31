import { useState, useEffect } from 'react'
import { Card, Table, Tag, Button, Space, Tabs, Modal, Input, message, Typography, Spin, Alert } from 'antd'
import { CheckOutlined, CloseOutlined, QuestionCircleOutlined, EyeOutlined, DownloadOutlined, FileTextOutlined, FilePdfOutlined, FileImageOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reviewApi, Contribution } from '../api'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

// ==================== Preview Modal Component ====================
interface PreviewModalProps {
  visible: boolean
  item: Contribution | null
  onClose: () => void
  onApprove: (id: number) => void
  onReject: (id: number) => void
  isApproving: boolean
  typeLabels: Record<string, string>
}

function PreviewModal({ visible, item, onClose, onApprove, onReject, isApproving, typeLabels }: PreviewModalProps) {
  const [previewData, setPreviewData] = useState<{
    url?: string
    content?: string
    mime_type?: string
    type?: string
    loading: boolean
    error?: string
  }>({ loading: false })

  // Fetch preview data when modal opens
  useEffect(() => {
    if (visible && item) {
      loadPreview(item)
    } else {
      setPreviewData({ loading: false })
    }
  }, [visible, item])

  const loadPreview = async (contribution: Contribution) => {
    setPreviewData({ loading: true })
    
    try {
      // For draft KUs or text files, try to get content first
      const contentResult = await reviewApi.getFileContent(contribution.id)
      
      if (contentResult.content) {
        setPreviewData({
          content: contentResult.content,
          mime_type: contentResult.mime_type,
          type: contentResult.type,
          loading: false
        })
      } else {
        // For binary files, get preview URL
        const previewResult = await reviewApi.getPreviewUrl(contribution.id)
        setPreviewData({
          url: previewResult.url,
          mime_type: previewResult.mime_type,
          type: 'binary',
          loading: false
        })
      }
    } catch (error) {
      console.error('Failed to load preview:', error)
      setPreviewData({
        loading: false,
        error: '无法加载预览'
      })
    }
  }

  const renderPreview = () => {
    if (previewData.loading) {
      return (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <p style={{ marginTop: 16, color: '#94a3b8' }}>加载预览中...</p>
        </div>
      )
    }

    if (previewData.error) {
      return (
        <Alert type="warning" message={previewData.error} />
      )
    }

    if (previewData.content) {
      // Text content preview
      return (
        <div style={{ 
          background: '#0f172a', 
          borderRadius: 8, 
          padding: 16, 
          maxHeight: 400, 
          overflow: 'auto',
          fontFamily: 'monospace',
          fontSize: 13,
          whiteSpace: 'pre-wrap',
          color: '#e2e8f0'
        }}>
          {previewData.content}
        </div>
      )
    }

    if (previewData.url) {
      const mime = previewData.mime_type || ''
      
      // Image preview
      if (mime.startsWith('image/')) {
        return (
          <div style={{ textAlign: 'center' }}>
            <img 
              src={previewData.url} 
              alt="Preview" 
              style={{ maxWidth: '100%', maxHeight: 400, borderRadius: 8 }}
            />
          </div>
        )
      }
      
      // PDF preview (iframe)
      if (mime === 'application/pdf') {
        return (
          <div>
            <iframe 
              src={previewData.url} 
              style={{ width: '100%', height: 500, border: 'none', borderRadius: 8 }}
              title="PDF Preview"
            />
            <div style={{ marginTop: 8, textAlign: 'center' }}>
              <Button icon={<DownloadOutlined />} href={previewData.url} target="_blank">
                下载 PDF
              </Button>
            </div>
          </div>
        )
      }
      
      // Other binary files - download link
      return (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <FilePdfOutlined style={{ fontSize: 48, color: '#64748b' }} />
          <p style={{ marginTop: 16, color: '#94a3b8' }}>
            此文件类型不支持在线预览
          </p>
          <Button type="primary" icon={<DownloadOutlined />} href={previewData.url} target="_blank">
            下载文件查看
          </Button>
        </div>
      )
    }

    // No file attached (draft only)
    if (item?.contribution_type === 'signal' || item?.contribution_type === 'draft_ku') {
      return (
        <div style={{ 
          background: '#1e293b', 
          borderRadius: 8, 
          padding: 16,
          color: '#94a3b8'
        }}>
          <Text type="secondary">这是一个草稿/信号贡献，无附件文件</Text>
        </div>
      )
    }

    return (
      <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>
        无法加载预览
      </div>
    )
  }

  if (!item) return null

  return (
    <Modal
      title={item.title || '贡献详情'}
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
        item.status === 'pending' && (
          <Button
            key="reject"
            danger
            onClick={() => onReject(item.id)}
          >
            拒绝
          </Button>
        ),
        item.status === 'pending' && (
          <Button
            key="approve"
            type="primary"
            loading={isApproving}
            onClick={() => onApprove(item.id)}
          >
            批准
          </Button>
        ),
      ].filter(Boolean)}
      width={900}
    >
      <div style={{ marginBottom: 16 }}>
        <Space wrap>
          <Tag color="blue">{typeLabels[item.contribution_type] || item.contribution_type}</Tag>
          {item.ku_type_code && <Tag color="green">{item.ku_type_code}</Tag>}
          {item.product_id && <Tag color="purple">{item.product_id}</Tag>}
          <Tag>{item.visibility}</Tag>
        </Space>
      </div>
      
      <div style={{ marginBottom: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div><Text type="secondary">贡献者:</Text> <Text strong>{item.contributor_name}</Text></div>
        <div><Text type="secondary">提交时间:</Text> <Text>{item.created_at}</Text></div>
        {item.file_name && (
          <div><Text type="secondary">文件:</Text> <Text>{item.file_name} ({Math.round((item.file_size || 0) / 1024)} KB)</Text></div>
        )}
        {item.trigger_type && (
          <div><Text type="secondary">触发场景:</Text> <Text>{item.trigger_type}</Text></div>
        )}
      </div>
      
      {item.description && (
        <Paragraph>
          <Text type="secondary">描述: </Text>
          {item.description}
        </Paragraph>
      )}
      
      {item.query_text && (
        <Paragraph>
          <Text type="secondary">触发问题: </Text>
          <Text code>{item.query_text}</Text>
        </Paragraph>
      )}
      
      {item.review_comment && (
        <Alert
          type="info"
          message="审核意见"
          description={item.review_comment}
          style={{ marginBottom: 16 }}
        />
      )}
      
      <div style={{ marginTop: 16 }}>
        <Text type="secondary" style={{ marginBottom: 8, display: 'block' }}>文件预览:</Text>
        {renderPreview()}
      </div>
    </Modal>
  )
}

// ==================== Main Review Component ====================
export default function Review() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('pending')
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [previewModal, setPreviewModal] = useState<{ visible: boolean; item: Contribution | null }>({
    visible: false,
    item: null,
  })
  const [rejectModal, setRejectModal] = useState<{ visible: boolean; id: number | null }>({
    visible: false,
    id: null,
  })
  const [infoModal, setInfoModal] = useState<{ visible: boolean; id: number | null }>({
    visible: false,
    id: null,
  })
  const [rejectReason, setRejectReason] = useState('')
  const [infoQuestions, setInfoQuestions] = useState('')
  
  // Fetch contributions based on status
  const { data: queueData, isLoading } = useQuery({
    queryKey: ['review-queue', activeTab],
    queryFn: () => reviewApi.getQueue({ status_filter: activeTab, limit: 50 }),
  })
  
  // Fetch stats for tab labels
  const { data: statsData } = useQuery({
    queryKey: ['review-stats'],
    queryFn: () => reviewApi.getStats(),
  })
  
  // Mutations
  const approveMutation = useMutation({
    mutationFn: (id: number) => reviewApi.approve(id),
    onSuccess: () => {
      message.success('贡献已批准')
      queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      queryClient.invalidateQueries({ queryKey: ['review-stats'] })
    },
    onError: () => message.error('操作失败'),
  })
  
  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) => reviewApi.reject(id, reason),
    onSuccess: () => {
      message.success('贡献已拒绝')
      queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      queryClient.invalidateQueries({ queryKey: ['review-stats'] })
      setRejectModal({ visible: false, id: null })
      setRejectReason('')
    },
    onError: () => message.error('操作失败'),
  })
  
  const requestInfoMutation = useMutation({
    mutationFn: ({ id, questions }: { id: number; questions: string }) => reviewApi.requestInfo(id, questions),
    onSuccess: () => {
      message.success('已请求补充信息')
      queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      queryClient.invalidateQueries({ queryKey: ['review-stats'] })
      setInfoModal({ visible: false, id: null })
      setInfoQuestions('')
    },
    onError: () => message.error('操作失败'),
  })
  
  const batchMutation = useMutation({
    mutationFn: ({ ids, action }: { ids: number[]; action: 'approve' | 'reject' }) => 
      reviewApi.batchReview(ids, action),
    onSuccess: (data) => {
      message.success(`批量操作完成，处理 ${data.processed} 项`)
      queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      queryClient.invalidateQueries({ queryKey: ['review-stats'] })
      setSelectedRowKeys([])
    },
    onError: () => message.error('批量操作失败'),
  })
  
  const handleApprove = (id: number) => {
    approveMutation.mutate(id)
  }
  
  const handleReject = () => {
    if (!rejectReason.trim()) {
      message.error('请填写拒绝原因')
      return
    }
    if (rejectModal.id) {
      rejectMutation.mutate({ id: rejectModal.id, reason: rejectReason })
    }
  }
  
  const handleRequestInfo = () => {
    if (!infoQuestions.trim()) {
      message.error('请填写需要补充的问题')
      return
    }
    if (infoModal.id) {
      requestInfoMutation.mutate({ id: infoModal.id, questions: infoQuestions })
    }
  }
  
  const typeLabels: Record<string, string> = {
    'file_upload': '文件上传',
    'draft_ku': '草稿 KU',
    'signal': '现场信号',
    'feedback': '反馈',
    'correction': '修正',
  }
  
  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      render: (text: string, record: Contribution) => (
        <a onClick={() => setPreviewModal({ visible: true, item: record })}>{text || '未命名'}</a>
      ),
    },
    { title: '贡献者', dataIndex: 'contributor_name', key: 'contributor_name' },
    {
      title: '类型',
      dataIndex: 'ku_type_code',
      key: 'ku_type_code',
      render: (type: string) => <Tag color="blue">{type || '-'}</Tag>,
    },
    { title: '产品', dataIndex: 'product_id', key: 'product_id', render: (p: string) => p || '-' },
    { 
      title: '触发场景', 
      dataIndex: 'trigger_type', 
      key: 'trigger_type',
      render: (t: string) => {
        const triggerLabels: Record<string, string> = {
          'missing_info': '缺资料提示',
          'improve_response': '回答改进',
          'high_value_signal': '高价值信号',
        }
        return triggerLabels[t] || t || '-'
      }
    },
    { title: '提交时间', dataIndex: 'created_at', key: 'created_at' },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: Contribution) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => setPreviewModal({ visible: true, item: record })}
          >
            预览
          </Button>
          {record.status === 'pending' && (
            <>
              <Button
                type="link"
                icon={<CheckOutlined />}
                style={{ color: '#22c55e' }}
                onClick={() => handleApprove(record.id)}
                loading={approveMutation.isPending}
              >
                批准
              </Button>
              <Button
                type="link"
                icon={<CloseOutlined />}
                danger
                onClick={() => setRejectModal({ visible: true, id: record.id })}
              >
                拒绝
              </Button>
              <Button 
                type="link" 
                icon={<QuestionCircleOutlined />}
                onClick={() => setInfoModal({ visible: true, id: record.id })}
              >
                请求补充
              </Button>
            </>
          )}
        </Space>
      ),
    },
  ]
  
  const tabItems = [
    {
      key: 'pending',
      label: `待审核 (${statsData?.total_pending ?? 0})`,
      children: (
        <Table
          rowSelection={{
            selectedRowKeys,
            onChange: setSelectedRowKeys,
          }}
          dataSource={queueData?.contributions ?? []}
          columns={columns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          loading={isLoading}
          locale={{ emptyText: '暂无待审核项' }}
        />
      ),
    },
    {
      key: 'approved',
      label: `已审核 (${statsData?.total_approved ?? 0})`,
      children: (
        <Table 
          dataSource={queueData?.contributions ?? []} 
          columns={columns} 
          rowKey="id" 
          loading={isLoading}
          locale={{ emptyText: '暂无已审核项' }}
        />
      ),
    },
    {
      key: 'rejected',
      label: `已拒绝 (${statsData?.total_rejected ?? 0})`,
      children: (
        <Table 
          dataSource={queueData?.contributions ?? []} 
          columns={columns} 
          rowKey="id" 
          loading={isLoading}
          locale={{ emptyText: '暂无已拒绝项' }}
        />
      ),
    },
    {
      key: 'needs_info',
      label: `待补充 (${statsData?.needs_info ?? 0})`,
      children: (
        <Table 
          dataSource={queueData?.contributions ?? []} 
          columns={columns} 
          rowKey="id" 
          loading={isLoading}
          locale={{ emptyText: '暂无待补充项' }}
        />
      ),
    },
  ]
  
  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>贡献审核</Title>
      
      <Card>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Button
              type="primary"
              disabled={selectedRowKeys.length === 0}
              loading={batchMutation.isPending}
              onClick={() => batchMutation.mutate({ 
                ids: selectedRowKeys as number[], 
                action: 'approve' 
              })}
            >
              批量批准 ({selectedRowKeys.length})
            </Button>
            <Button
              danger
              disabled={selectedRowKeys.length === 0}
              loading={batchMutation.isPending}
              onClick={() => batchMutation.mutate({ 
                ids: selectedRowKeys as number[], 
                action: 'reject' 
              })}
            >
              批量拒绝 ({selectedRowKeys.length})
            </Button>
          </Space>
        </div>
        
        <Tabs 
          items={tabItems} 
          activeKey={activeTab}
          onChange={(key) => {
            setActiveTab(key)
            setSelectedRowKeys([])
          }}
        />
      </Card>
      
      {/* Preview Modal */}
      <PreviewModal
        visible={previewModal.visible}
        item={previewModal.item}
        onClose={() => setPreviewModal({ visible: false, item: null })}
        onApprove={(id) => {
          handleApprove(id)
          setPreviewModal({ visible: false, item: null })
        }}
        onReject={(id) => {
          setPreviewModal({ visible: false, item: null })
          setRejectModal({ visible: true, id })
        }}
        isApproving={approveMutation.isPending}
        typeLabels={typeLabels}
      />
      
      {/* Reject Modal */}
      <Modal
        title="拒绝原因"
        open={rejectModal.visible}
        onCancel={() => setRejectModal({ visible: false, id: null })}
        onOk={handleReject}
        okText="确认拒绝"
        okButtonProps={{ danger: true, loading: rejectMutation.isPending }}
      >
        <TextArea
          rows={4}
          placeholder="请填写拒绝原因，将反馈给贡献者"
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
        />
      </Modal>
      
      {/* Request Info Modal */}
      <Modal
        title="请求补充信息"
        open={infoModal.visible}
        onCancel={() => setInfoModal({ visible: false, id: null })}
        onOk={handleRequestInfo}
        okText="发送请求"
        okButtonProps={{ loading: requestInfoMutation.isPending }}
      >
        <TextArea
          rows={4}
          placeholder="请填写需要贡献者补充的问题或信息"
          value={infoQuestions}
          onChange={(e) => setInfoQuestions(e.target.value)}
        />
      </Modal>
    </div>
  )
}
