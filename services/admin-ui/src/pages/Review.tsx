import { useState } from 'react'
import { Card, Table, Tag, Button, Space, Tabs, Modal, Input, message, Typography } from 'antd'
import { CheckOutlined, CloseOutlined, QuestionCircleOutlined, EyeOutlined } from '@ant-design/icons'

const { Title } = Typography
const { TextArea } = Input

// Mock data
const mockContributions = [
  {
    id: 1,
    title: '华为PCB产线案例.pdf',
    contributor: '张三',
    type: 'file_upload',
    ku_type: '客户案例',
    product: 'AOI8000',
    trigger: '缺资料提示',
    status: 'pending',
    created_at: '2024-01-20 14:30',
  },
  {
    id: 2,
    title: 'AOI选型话术补充.txt',
    contributor: '李明',
    type: 'draft_ku',
    ku_type: '销售话术',
    product: '通用',
    trigger: '回答不够销售化',
    status: 'pending',
    created_at: '2024-01-20 10:15',
  },
  {
    id: 3,
    title: '客户成交案例卡',
    contributor: '王五',
    type: 'signal',
    ku_type: '现场信号',
    product: 'AOI8000',
    trigger: '高价值信号识别',
    status: 'pending',
    created_at: '2024-01-19 16:45',
  },
]

export default function Review() {
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [previewModal, setPreviewModal] = useState<{ visible: boolean; item: typeof mockContributions[0] | null }>({
    visible: false,
    item: null,
  })
  const [rejectModal, setRejectModal] = useState<{ visible: boolean; id: number | null }>({
    visible: false,
    id: null,
  })
  const [rejectReason, setRejectReason] = useState('')
  
  const handleApprove = (id: number) => {
    message.success(`贡献 #${id} 已批准`)
  }
  
  const handleReject = () => {
    if (!rejectReason.trim()) {
      message.error('请填写拒绝原因')
      return
    }
    message.success(`贡献 #${rejectModal.id} 已拒绝`)
    setRejectModal({ visible: false, id: null })
    setRejectReason('')
  }
  
  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      render: (text: string, record: typeof mockContributions[0]) => (
        <a onClick={() => setPreviewModal({ visible: true, item: record })}>{text}</a>
      ),
    },
    { title: '贡献者', dataIndex: 'contributor', key: 'contributor' },
    {
      title: '类型',
      dataIndex: 'ku_type',
      key: 'ku_type',
      render: (type: string) => <Tag color="blue">{type}</Tag>,
    },
    { title: '产品', dataIndex: 'product', key: 'product' },
    { title: '触发场景', dataIndex: 'trigger', key: 'trigger' },
    { title: '提交时间', dataIndex: 'created_at', key: 'created_at' },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: typeof mockContributions[0]) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => setPreviewModal({ visible: true, item: record })}
          >
            预览
          </Button>
          <Button
            type="link"
            icon={<CheckOutlined />}
            style={{ color: '#22c55e' }}
            onClick={() => handleApprove(record.id)}
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
          <Button type="link" icon={<QuestionCircleOutlined />}>
            请求补充
          </Button>
        </Space>
      ),
    },
  ]
  
  const tabItems = [
    {
      key: 'pending',
      label: `待审核 (${mockContributions.length})`,
      children: (
        <Table
          rowSelection={{
            selectedRowKeys,
            onChange: setSelectedRowKeys,
          }}
          dataSource={mockContributions}
          columns={columns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      ),
    },
    {
      key: 'approved',
      label: '已审核',
      children: <Table dataSource={[]} columns={columns} rowKey="id" />,
    },
    {
      key: 'rejected',
      label: '已拒绝',
      children: <Table dataSource={[]} columns={columns} rowKey="id" />,
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
              onClick={() => message.success(`批量批准 ${selectedRowKeys.length} 项`)}
            >
              批量批准 ({selectedRowKeys.length})
            </Button>
            <Button
              danger
              disabled={selectedRowKeys.length === 0}
              onClick={() => message.success(`批量拒绝 ${selectedRowKeys.length} 项`)}
            >
              批量拒绝 ({selectedRowKeys.length})
            </Button>
          </Space>
        </div>
        
        <Tabs items={tabItems} />
      </Card>
      
      {/* Preview Modal */}
      <Modal
        title={previewModal.item?.title}
        open={previewModal.visible}
        onCancel={() => setPreviewModal({ visible: false, item: null })}
        footer={[
          <Button key="close" onClick={() => setPreviewModal({ visible: false, item: null })}>
            关闭
          </Button>,
          <Button
            key="reject"
            danger
            onClick={() => {
              setPreviewModal({ visible: false, item: null })
              setRejectModal({ visible: true, id: previewModal.item?.id || null })
            }}
          >
            拒绝
          </Button>,
          <Button
            key="approve"
            type="primary"
            onClick={() => {
              if (previewModal.item) {
                handleApprove(previewModal.item.id)
                setPreviewModal({ visible: false, item: null })
              }
            }}
          >
            批准
          </Button>,
        ]}
        width={800}
      >
        {previewModal.item && (
          <div>
            <p><strong>贡献者:</strong> {previewModal.item.contributor}</p>
            <p><strong>类型:</strong> {previewModal.item.ku_type}</p>
            <p><strong>产品:</strong> {previewModal.item.product}</p>
            <p><strong>触发场景:</strong> {previewModal.item.trigger}</p>
            <p><strong>提交时间:</strong> {previewModal.item.created_at}</p>
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
        okButtonProps={{ danger: true }}
      >
        <TextArea
          rows={4}
          placeholder="请填写拒绝原因，将反馈给贡献者"
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
        />
      </Modal>
    </div>
  )
}

