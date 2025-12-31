import { useState } from 'react'
import { Card, Table, Tag, Button, Space, Tabs, Modal, Input, message, Typography } from 'antd'
import { CheckOutlined, CloseOutlined, QuestionCircleOutlined, EyeOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reviewApi, Contribution } from '../api'

const { Title } = Typography
const { TextArea } = Input

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
      <Modal
        title={previewModal.item?.title || '贡献详情'}
        open={previewModal.visible}
        onCancel={() => setPreviewModal({ visible: false, item: null })}
        footer={[
          <Button key="close" onClick={() => setPreviewModal({ visible: false, item: null })}>
            关闭
          </Button>,
          previewModal.item?.status === 'pending' && (
            <Button
              key="reject"
              danger
              onClick={() => {
                setPreviewModal({ visible: false, item: null })
                setRejectModal({ visible: true, id: previewModal.item?.id || null })
              }}
            >
              拒绝
            </Button>
          ),
          previewModal.item?.status === 'pending' && (
            <Button
              key="approve"
              type="primary"
              loading={approveMutation.isPending}
              onClick={() => {
                if (previewModal.item) {
                  handleApprove(previewModal.item.id)
                  setPreviewModal({ visible: false, item: null })
                }
              }}
            >
              批准
            </Button>
          ),
        ].filter(Boolean)}
        width={800}
      >
        {previewModal.item && (
          <div>
            <p><strong>贡献者:</strong> {previewModal.item.contributor_name}</p>
            <p><strong>贡献类型:</strong> {typeLabels[previewModal.item.contribution_type] || previewModal.item.contribution_type}</p>
            <p><strong>KU 类型:</strong> {previewModal.item.ku_type_code || '-'}</p>
            <p><strong>产品:</strong> {previewModal.item.product_id || '-'}</p>
            <p><strong>触发场景:</strong> {previewModal.item.trigger_type || '-'}</p>
            <p><strong>提交时间:</strong> {previewModal.item.created_at}</p>
            {previewModal.item.description && (
              <p><strong>描述:</strong> {previewModal.item.description}</p>
            )}
            {previewModal.item.query_text && (
              <p><strong>触发问题:</strong> {previewModal.item.query_text}</p>
            )}
            {previewModal.item.file_name && (
              <p><strong>文件:</strong> {previewModal.item.file_name} ({Math.round((previewModal.item.file_size || 0) / 1024)} KB)</p>
            )}
            {previewModal.item.review_comment && (
              <p><strong>审核意见:</strong> {previewModal.item.review_comment}</p>
            )}
            <div style={{ marginTop: 16, padding: 16, background: '#1e293b', borderRadius: 8 }}>
              <p style={{ color: '#94a3b8' }}>文件预览区域（实际实现需要根据文件类型显示内容）</p>
            </div>
          </div>
        )}
      </Modal>
      
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
