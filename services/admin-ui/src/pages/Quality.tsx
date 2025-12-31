import { useState } from 'react'
import { Card, Typography, Table, Row, Col, Statistic, Progress, Spin, Tag, Tabs, Modal, Form, Input, Select, message } from 'antd'
import { 
  CheckCircleOutlined, 
  ExclamationCircleOutlined, 
  LineChartOutlined,
  ThunderboltOutlined 
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { statsApi, tasksApi } from '../api'

const { Title, Text } = Typography
const { TextArea } = Input

function QualityOverview() {
  const { data: qualityData, isLoading } = useQuery({
    queryKey: ['quality-stats'],
    queryFn: () => statsApi.getQuality(),
  })
  
  return (
    <Spin spinning={isLoading}>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic 
              title="DQ 通过率" 
              value={qualityData?.dq_pass_rate || 0} 
              suffix="%" 
              precision={1}
              valueStyle={{ color: (qualityData?.dq_pass_rate || 0) >= 80 ? '#22c55e' : '#ef4444' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="总 DQ 运行次数" 
              value={qualityData?.total_dq_runs || 0}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="KU 类型数" 
              value={Object.keys(qualityData?.ku_type_distribution || {}).length}
              prefix={<LineChartOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="已发布 KU" 
              value={qualityData?.ku_status_distribution?.published || 0}
              valueStyle={{ color: '#22c55e' }}
            />
          </Card>
        </Col>
      </Row>
      
      <Row gutter={16}>
        <Col span={12}>
          <Card title="KU 类型分布">
            {qualityData?.ku_type_distribution && Object.keys(qualityData.ku_type_distribution).length > 0 ? (
              <div>
                {Object.entries(qualityData.ku_type_distribution).map(([type, count]) => (
                  <div key={type} style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text>{type}</Text>
                      <Text strong>{count as number}</Text>
                    </div>
                    <Progress 
                      percent={Math.round((count as number) / Object.values(qualityData.ku_type_distribution).reduce((a, b) => (a as number) + (b as number), 0) * 100)} 
                      showInfo={false}
                      strokeColor="#3b82f6"
                    />
                  </div>
                ))}
              </div>
            ) : (
              <Text type="secondary">暂无数据</Text>
            )}
          </Card>
        </Col>
        <Col span={12}>
          <Card title="KU 状态分布">
            {qualityData?.ku_status_distribution && Object.keys(qualityData.ku_status_distribution).length > 0 ? (
              <div>
                {Object.entries(qualityData.ku_status_distribution).map(([status, count]) => {
                  const colors: Record<string, string> = {
                    published: '#22c55e',
                    draft: '#eab308',
                    pending: '#3b82f6',
                    rejected: '#ef4444',
                  }
                  return (
                    <div key={status} style={{ marginBottom: 12 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Text>{status}</Text>
                        <Text strong>{count as number}</Text>
                      </div>
                      <Progress 
                        percent={Math.round((count as number) / Object.values(qualityData.ku_status_distribution).reduce((a, b) => (a as number) + (b as number), 0) * 100)} 
                        showInfo={false}
                        strokeColor={colors[status] || '#64748b'}
                      />
                    </div>
                  )
                })}
              </div>
            ) : (
              <Text type="secondary">暂无数据</Text>
            )}
          </Card>
        </Col>
      </Row>
    </Spin>
  )
}

interface FeedbackItem {
  id: string
  query: string
  feedback: string
  reason: string
  date: string
  conversation_id?: string
}

function FeedbackAnalysis() {
  const queryClient = useQueryClient()
  const [taskModal, setTaskModal] = useState<{ visible: boolean; item: FeedbackItem | null }>({
    visible: false,
    item: null,
  })
  const [taskForm] = Form.useForm()
  
  // Fetch feedback data - using stats API
  const { data: feedbackStats, isLoading } = useQuery({
    queryKey: ['feedback-stats'],
    queryFn: () => statsApi.getFeedback(),
  })
  
  // Create task mutation
  const createTaskMutation = useMutation({
    mutationFn: tasksApi.create,
    onSuccess: () => {
      message.success('优化任务已创建')
      setTaskModal({ visible: false, item: null })
      taskForm.resetFields()
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: () => message.error('创建任务失败'),
  })
  
  const handleCreateTask = (item: FeedbackItem) => {
    setTaskModal({ visible: true, item })
    taskForm.setFieldsValue({
      title: `优化反馈: ${item.query.substring(0, 30)}...`,
      description: `用户问题: ${item.query}\n反馈原因: ${item.reason}`,
      task_type: 'review_ku',
      priority: 'normal',
    })
  }
  
  const handleSubmitTask = () => {
    taskForm.validateFields().then((values) => {
      createTaskMutation.mutate({
        ...values,
        related_type: 'feedback',
        related_id: taskModal.item?.id ? parseInt(taskModal.item.id) : undefined,
      })
    })
  }
  
  // Use API data
  const negativeFeedback: FeedbackItem[] = feedbackStats?.negative_feedback ?? []
  
  const columns = [
    { title: '问题', dataIndex: 'query', key: 'query', ellipsis: true },
    { 
      title: '反馈', 
      dataIndex: 'feedback', 
      key: 'feedback',
      render: (fb: string) => (
        <Tag color={fb === 'positive' ? 'green' : 'red'}>
          {fb === 'positive' ? '👍 有帮助' : '👎 没帮助'}
        </Tag>
      ),
    },
    { title: '原因', dataIndex: 'reason', key: 'reason' },
    { title: '日期', dataIndex: 'date', key: 'date' },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: FeedbackItem) => (
        <a onClick={() => handleCreateTask(record)}>创建优化任务</a>
      ),
    },
  ]
  
  return (
    <div>
      <Spin spinning={isLoading}>
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={8}>
            <Card>
              <Statistic 
                title="正面反馈" 
                value={feedbackStats?.positive_rate ?? 85} 
                suffix="%" 
                valueStyle={{ color: '#22c55e' }} 
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic 
                title="负面反馈" 
                value={feedbackStats?.negative_rate ?? 15} 
                suffix="%" 
                valueStyle={{ color: '#ef4444' }} 
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic 
                title="待处理反馈" 
                value={feedbackStats?.pending_count ?? 12} 
              />
            </Card>
          </Col>
        </Row>
        
        <Card title="负面反馈列表">
          <Table 
            dataSource={negativeFeedback} 
            columns={columns} 
            rowKey="id"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: '暂无负面反馈' }}
          />
        </Card>
      </Spin>
      
      {/* Create Task Modal */}
      <Modal
        title="创建优化任务"
        open={taskModal.visible}
        onCancel={() => setTaskModal({ visible: false, item: null })}
        onOk={handleSubmitTask}
        confirmLoading={createTaskMutation.isPending}
      >
        <Form form={taskForm} layout="vertical">
          <Form.Item 
            label="任务标题" 
            name="title" 
            rules={[{ required: true, message: '请输入任务标题' }]}
          >
            <Input />
          </Form.Item>
          
          <Form.Item 
            label="任务描述" 
            name="description"
          >
            <TextArea rows={4} />
          </Form.Item>
          
          <Form.Item label="任务类型" name="task_type">
            <Select>
              <Select.Option value="review_ku">审核 KU</Select.Option>
              <Select.Option value="request_info">请求信息</Select.Option>
              <Select.Option value="verify_content">验证内容</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="优先级" name="priority">
            <Select>
              <Select.Option value="low">低</Select.Option>
              <Select.Option value="normal">普通</Select.Option>
              <Select.Option value="high">高</Select.Option>
              <Select.Option value="urgent">紧急</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

interface DQRunItem {
  id: number
  ku_id: string
  passed: boolean
  reasons: string[]
  date: string
  details?: {
    title?: string
    ku_type?: string
    checks?: { name: string; passed: boolean; message?: string }[]
  }
}

function DQReport() {
  const [detailModal, setDetailModal] = useState<{ visible: boolean; item: DQRunItem | null }>({
    visible: false,
    item: null,
  })
  
  // Fetch DQ runs from API
  const { data: dqData, isLoading } = useQuery({
    queryKey: ['dq-runs'],
    queryFn: () => statsApi.getDQRuns({ limit: 20 }),
  })
  
  const dqRuns = dqData?.runs ?? []
  
  const handleViewDetails = (record: DQRunItem) => {
    setDetailModal({ visible: true, item: record })
  }
  
  const columns = [
    { title: 'KU ID', dataIndex: 'ku_id', key: 'ku_id' },
    { 
      title: '结果', 
      dataIndex: 'passed', 
      key: 'passed',
      render: (passed: boolean) => (
        passed ? 
          <Tag color="green" icon={<CheckCircleOutlined />}>通过</Tag> :
          <Tag color="red" icon={<ExclamationCircleOutlined />}>失败</Tag>
      ),
    },
    { 
      title: '失败原因', 
      dataIndex: 'reasons', 
      key: 'reasons',
      render: (reasons: string[]) => reasons.length > 0 ? reasons.join(', ') : '-',
    },
    { title: '时间', dataIndex: 'date', key: 'date' },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: DQRunItem) => (
        record.passed ? '-' : <a onClick={() => handleViewDetails(record)}>查看详情</a>
      ),
    },
  ]
  
  return (
    <div>
      <Spin spinning={isLoading}>
        <Card title="DQ 检查记录" extra={<a href="/quality">查看全部</a>}>
          <Table 
            dataSource={dqRuns} 
            columns={columns} 
            rowKey="id"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: '暂无 DQ 检查记录' }}
          />
        </Card>
      </Spin>
      
      {/* DQ Details Modal */}
      <Modal
        title={`DQ 检查详情 - ${detailModal.item?.ku_id || ''}`}
        open={detailModal.visible}
        onCancel={() => setDetailModal({ visible: false, item: null })}
        footer={null}
        width={600}
      >
        {detailModal.item?.details && (
          <div>
            <p><strong>标题:</strong> {detailModal.item.details.title}</p>
            <p><strong>类型:</strong> {detailModal.item.details.ku_type}</p>
            <p><strong>检查时间:</strong> {detailModal.item.date}</p>
            
            <div style={{ marginTop: 16 }}>
              <Text strong>检查项列表:</Text>
              <Table
                dataSource={detailModal.item.details.checks}
                columns={[
                  { title: '检查项', dataIndex: 'name', key: 'name' },
                  { 
                    title: '结果', 
                    dataIndex: 'passed', 
                    key: 'passed',
                    render: (passed: boolean) => (
                      passed ? 
                        <Tag color="green">✓ 通过</Tag> :
                        <Tag color="red">✗ 失败</Tag>
                    ),
                  },
                  { 
                    title: '说明', 
                    dataIndex: 'message', 
                    key: 'message',
                    render: (msg: string) => msg || '-',
                  },
                ]}
                rowKey="name"
                pagination={false}
                size="small"
                style={{ marginTop: 8 }}
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

function RegressionTest() {
  // Placeholder for regression testing
  return (
    <div>
      <Card>
        <div style={{ textAlign: 'center', padding: 40 }}>
          <ExclamationCircleOutlined style={{ fontSize: 48, color: '#64748b', marginBottom: 16 }} />
          <Title level={4} type="secondary">回归测试功能待实现</Title>
          <Text type="secondary">
            计划功能：多轮对话回归测试、答案质量评估、自动化测试用例管理
          </Text>
        </div>
      </Card>
    </div>
  )
}

export default function Quality() {
  const tabItems = [
    { key: 'overview', label: '质量概览', children: <QualityOverview /> },
    { key: 'feedback', label: '反馈分析', children: <FeedbackAnalysis /> },
    { key: 'dq', label: 'DQ 报告', children: <DQReport /> },
    { key: 'regression', label: '回归测试', children: <RegressionTest /> },
  ]
  
  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>质量分析</Title>
      
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  )
}

