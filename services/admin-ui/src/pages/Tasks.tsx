import { useState } from 'react'
import { 
  Card, 
  Table, 
  Button, 
  Space, 
  Tag, 
  Modal, 
  Form, 
  Input, 
  Select, 
  DatePicker, 
  message, 
  Typography,
  Spin,
  Tabs,
  Badge,
  Descriptions,
  Statistic,
  Row,
  Col
} from 'antd'
import { 
  PlusOutlined, 
  CheckCircleOutlined, 
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  UserOutlined
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tasksApi, Task, CreateTaskRequest } from '../api'
import dayjs from 'dayjs'

const { Title, Text } = Typography
const { TextArea } = Input

export default function Tasks() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('all')
  const [createModal, setCreateModal] = useState(false)
  const [detailModal, setDetailModal] = useState<{ visible: boolean; task: Task | null }>({ 
    visible: false, 
    task: null 
  })
  const [resolveModal, setResolveModal] = useState<{ visible: boolean; task: Task | null }>({ 
    visible: false, 
    task: null 
  })
  const [form] = Form.useForm()
  const [resolveForm] = Form.useForm()
  
  // Get status filter based on active tab
  const getStatusFilter = () => {
    switch (activeTab) {
      case 'open': return 'open'
      case 'in_progress': return 'in_progress'
      case 'resolved': return 'resolved'
      default: return undefined
    }
  }
  
  // Fetch tasks
  const { data: tasksData, isLoading } = useQuery({
    queryKey: ['tasks', activeTab],
    queryFn: () => tasksApi.getTasks({ status_filter: getStatusFilter(), limit: 100 }),
  })
  
  // Fetch stats
  const { data: statsData } = useQuery({
    queryKey: ['task-stats'],
    queryFn: () => tasksApi.getTaskStats(),
  })
  
  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: CreateTaskRequest) => tasksApi.createTask(data),
    onSuccess: () => {
      message.success('任务创建成功')
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['task-stats'] })
      setCreateModal(false)
      form.resetFields()
    },
    onError: () => message.error('创建失败'),
  })
  
  const resolveMutation = useMutation({
    mutationFn: ({ taskId, resolution }: { taskId: number; resolution: string }) => 
      tasksApi.resolveTask(taskId, resolution),
    onSuccess: () => {
      message.success('任务已完成')
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['task-stats'] })
      setResolveModal({ visible: false, task: null })
      resolveForm.resetFields()
    },
    onError: () => message.error('操作失败'),
  })
  
  const cancelMutation = useMutation({
    mutationFn: (taskId: number) => tasksApi.cancelTask(taskId),
    onSuccess: () => {
      message.success('任务已取消')
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['task-stats'] })
    },
    onError: () => message.error('操作失败'),
  })
  
  const getStatusTag = (status: string) => {
    const configs: Record<string, { color: string; icon: React.ReactNode }> = {
      open: { color: 'blue', icon: <ClockCircleOutlined /> },
      in_progress: { color: 'orange', icon: <ExclamationCircleOutlined /> },
      resolved: { color: 'green', icon: <CheckCircleOutlined /> },
      cancelled: { color: 'default', icon: <CloseCircleOutlined /> },
    }
    const config = configs[status] || configs.open
    return <Tag color={config.color} icon={config.icon}>{status}</Tag>
  }
  
  const getPriorityTag = (priority: string) => {
    const colors: Record<string, string> = {
      low: 'default',
      normal: 'blue',
      high: 'orange',
      urgent: 'red',
    }
    return <Tag color={colors[priority] || 'default'}>{priority}</Tag>
  }
  
  const getTaskTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      request_info: '请求信息',
      verify_content: '验证内容',
      approve_term: '审批术语',
      review_ku: '审核KU',
    }
    return labels[type] || type
  }
  
  const columns = [
    { 
      title: 'ID', 
      dataIndex: 'id', 
      key: 'id',
      width: 60,
    },
    { 
      title: '标题', 
      dataIndex: 'title', 
      key: 'title',
      render: (title: string, record: Task) => (
        <Button 
          type="link" 
          style={{ padding: 0 }}
          onClick={() => setDetailModal({ visible: true, task: record })}
        >
          {title}
        </Button>
      ),
    },
    { 
      title: '类型', 
      dataIndex: 'task_type', 
      key: 'task_type',
      render: (type: string) => <Tag>{getTaskTypeLabel(type)}</Tag>,
    },
    { 
      title: '优先级', 
      dataIndex: 'priority', 
      key: 'priority',
      render: getPriorityTag,
    },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: getStatusTag,
    },
    { 
      title: '负责人', 
      dataIndex: 'assignee_name', 
      key: 'assignee_name',
      render: (name: string) => name || <Text type="secondary">未分配</Text>,
    },
    { 
      title: '创建时间', 
      dataIndex: 'created_at', 
      key: 'created_at',
      render: (date: string) => date ? dayjs(date).format('YYYY-MM-DD HH:mm') : '-',
    },
    { 
      title: '截止时间', 
      dataIndex: 'due_date', 
      key: 'due_date',
      render: (date: string) => {
        if (!date) return '-'
        const d = dayjs(date)
        const isOverdue = d.isBefore(dayjs()) 
        return <Text type={isOverdue ? 'danger' : undefined}>{d.format('YYYY-MM-DD')}</Text>
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: Task) => (
        <Space>
          {record.status === 'open' || record.status === 'in_progress' ? (
            <>
              <Button 
                type="link" 
                size="small"
                onClick={() => setResolveModal({ visible: true, task: record })}
              >
                完成
              </Button>
              <Button 
                type="link" 
                size="small" 
                danger
                onClick={() => {
                  Modal.confirm({
                    title: '确认取消任务？',
                    content: `任务: ${record.title}`,
                    onOk: () => cancelMutation.mutate(record.id),
                  })
                }}
              >
                取消
              </Button>
            </>
          ) : (
            <Button type="link" size="small" disabled>已处理</Button>
          )}
        </Space>
      ),
    },
  ]
  
  const tabItems = [
    { 
      key: 'all', 
      label: (
        <span>
          全部 <Badge count={statsData?.total_open || 0} style={{ marginLeft: 4 }} />
        </span>
      ), 
    },
    { 
      key: 'open', 
      label: (
        <span>
          待处理 <Badge count={statsData?.by_status?.open || 0} style={{ marginLeft: 4 }} />
        </span>
      ), 
    },
    { 
      key: 'in_progress', 
      label: (
        <span>
          进行中 <Badge count={statsData?.by_status?.in_progress || 0} style={{ marginLeft: 4 }} />
        </span>
      ), 
    },
    { key: 'resolved', label: '已完成' },
  ]
  
  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>任务协作</Title>
      
      {/* Stats Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic 
              title="待处理" 
              value={statsData?.by_status?.open || 0} 
              valueStyle={{ color: '#3b82f6' }}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="进行中" 
              value={statsData?.by_status?.in_progress || 0} 
              valueStyle={{ color: '#f59e0b' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="已逾期" 
              value={statsData?.overdue || 0} 
              valueStyle={{ color: '#ef4444' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="已完成" 
              value={statsData?.by_status?.resolved || 0} 
              valueStyle={{ color: '#22c55e' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>
      
      {/* Task List */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <Tabs 
            activeKey={activeTab} 
            onChange={setActiveTab} 
            items={tabItems}
            style={{ marginBottom: 0 }}
          />
          <Button 
            type="primary" 
            icon={<PlusOutlined />}
            onClick={() => setCreateModal(true)}
          >
            新建任务
          </Button>
        </div>
        
        <Spin spinning={isLoading}>
          <Table 
            dataSource={tasksData?.tasks ?? []} 
            columns={columns} 
            rowKey="id"
            pagination={{ pageSize: 20 }}
            locale={{ emptyText: '暂无任务' }}
          />
        </Spin>
      </Card>
      
      {/* Create Task Modal */}
      <Modal
        title="新建任务"
        open={createModal}
        onCancel={() => {
          setCreateModal(false)
          form.resetFields()
        }}
        onOk={() => {
          form.validateFields().then((values) => {
            const data: CreateTaskRequest = {
              ...values,
              due_date: values.due_date ? values.due_date.toISOString() : undefined,
            }
            createMutation.mutate(data)
          })
        }}
        confirmLoading={createMutation.isPending}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item 
            label="任务类型" 
            name="task_type" 
            rules={[{ required: true, message: '请选择任务类型' }]}
          >
            <Select placeholder="选择类型">
              <Select.Option value="request_info">请求信息</Select.Option>
              <Select.Option value="verify_content">验证内容</Select.Option>
              <Select.Option value="approve_term">审批术语</Select.Option>
              <Select.Option value="review_ku">审核KU</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item 
            label="标题" 
            name="title" 
            rules={[{ required: true, message: '请输入标题' }]}
          >
            <Input placeholder="任务标题" />
          </Form.Item>
          
          <Form.Item label="描述" name="description">
            <TextArea rows={3} placeholder="任务描述" />
          </Form.Item>
          
          <Form.Item label="优先级" name="priority" initialValue="normal">
            <Select>
              <Select.Option value="low">低</Select.Option>
              <Select.Option value="normal">普通</Select.Option>
              <Select.Option value="high">高</Select.Option>
              <Select.Option value="urgent">紧急</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="截止日期" name="due_date">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          
          <Form.Item label="关联类型" name="related_type">
            <Select allowClear placeholder="选择关联类型">
              <Select.Option value="ku">知识单元</Select.Option>
              <Select.Option value="contribution">贡献</Select.Option>
              <Select.Option value="prompt">Prompt</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="关联 ID" name="related_id">
            <Input type="number" placeholder="关联对象 ID" />
          </Form.Item>
        </Form>
      </Modal>
      
      {/* Task Detail Modal */}
      <Modal
        title="任务详情"
        open={detailModal.visible}
        onCancel={() => setDetailModal({ visible: false, task: null })}
        footer={
          detailModal.task && (detailModal.task.status === 'open' || detailModal.task.status === 'in_progress') ? (
            <Space>
              <Button onClick={() => setDetailModal({ visible: false, task: null })}>关闭</Button>
              <Button 
                type="primary"
                onClick={() => {
                  setDetailModal({ visible: false, task: null })
                  setResolveModal({ visible: true, task: detailModal.task })
                }}
              >
                完成任务
              </Button>
            </Space>
          ) : null
        }
        width={600}
      >
        {detailModal.task && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="ID">{detailModal.task.id}</Descriptions.Item>
            <Descriptions.Item label="类型">
              {getTaskTypeLabel(detailModal.task.task_type)}
            </Descriptions.Item>
            <Descriptions.Item label="标题" span={2}>{detailModal.task.title}</Descriptions.Item>
            <Descriptions.Item label="描述" span={2}>
              {detailModal.task.description || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="状态">{getStatusTag(detailModal.task.status)}</Descriptions.Item>
            <Descriptions.Item label="优先级">{getPriorityTag(detailModal.task.priority)}</Descriptions.Item>
            <Descriptions.Item label="负责人">
              {detailModal.task.assignee_name || '未分配'}
            </Descriptions.Item>
            <Descriptions.Item label="创建人">
              {detailModal.task.requester_name || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {detailModal.task.created_at ? dayjs(detailModal.task.created_at).format('YYYY-MM-DD HH:mm') : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="截止时间">
              {detailModal.task.due_date ? dayjs(detailModal.task.due_date).format('YYYY-MM-DD') : '-'}
            </Descriptions.Item>
            {detailModal.task.resolution && (
              <Descriptions.Item label="处理结果" span={2}>
                {detailModal.task.resolution}
              </Descriptions.Item>
            )}
            {detailModal.task.resolved_at && (
              <Descriptions.Item label="完成时间" span={2}>
                {dayjs(detailModal.task.resolved_at).format('YYYY-MM-DD HH:mm')}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>
      
      {/* Resolve Task Modal */}
      <Modal
        title="完成任务"
        open={resolveModal.visible}
        onCancel={() => {
          setResolveModal({ visible: false, task: null })
          resolveForm.resetFields()
        }}
        onOk={() => {
          resolveForm.validateFields().then((values) => {
            if (resolveModal.task) {
              resolveMutation.mutate({ 
                taskId: resolveModal.task.id, 
                resolution: values.resolution 
              })
            }
          })
        }}
        confirmLoading={resolveMutation.isPending}
      >
        <Form form={resolveForm} layout="vertical">
          <Form.Item 
            label="处理结果" 
            name="resolution" 
            rules={[{ required: true, message: '请输入处理结果' }]}
          >
            <TextArea rows={4} placeholder="描述任务处理结果..." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

