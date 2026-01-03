import { useState } from 'react'
import { Card, Typography, Table, Row, Col, Statistic, Progress, Spin, Tag, Tabs, Modal, Form, Input, Select, message, Button, Space, Popconfirm, Badge, Tooltip, Collapse, Alert } from 'antd'
import { 
  CheckCircleOutlined, 
  ExclamationCircleOutlined, 
  LineChartOutlined,
  ThunderboltOutlined,
  PlusOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  UploadOutlined,
  CheckOutlined,
  CloseOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { statsApi, tasksApi, regressionApi } from '../api'
import type { TestCase, TestCaseCreate, TestRun, TestResult } from '../api'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input
const { Panel } = Collapse

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
    mutationFn: tasksApi.createTask,
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

// ==================== Regression Test Components ====================

function TestCasesPanel() {
  const queryClient = useQueryClient()
  const [caseModal, setCaseModal] = useState<{ visible: boolean; editCase: TestCase | null }>({ visible: false, editCase: null })
  const [importModal, setImportModal] = useState(false)
  const [form] = Form.useForm()
  const [importText, setImportText] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>()

  const { data: cases = [], isLoading } = useQuery({
    queryKey: ['regression-cases', categoryFilter],
    queryFn: () => regressionApi.listCases({ category: categoryFilter, limit: 200 }),
  })

  const createMutation = useMutation({
    mutationFn: (data: TestCaseCreate) => regressionApi.createCase(data),
    onSuccess: () => {
      message.success('测试用例已创建')
      setCaseModal({ visible: false, editCase: null })
      form.resetFields()
      queryClient.invalidateQueries({ queryKey: ['regression-cases'] })
    },
    onError: () => message.error('创建失败'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: TestCaseCreate }) => regressionApi.updateCase(id, data),
    onSuccess: () => {
      message.success('测试用例已更新')
      setCaseModal({ visible: false, editCase: null })
      form.resetFields()
      queryClient.invalidateQueries({ queryKey: ['regression-cases'] })
    },
    onError: () => message.error('更新失败'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => regressionApi.deleteCase(id),
    onSuccess: () => {
      message.success('已删除')
      queryClient.invalidateQueries({ queryKey: ['regression-cases'] })
    },
    onError: () => message.error('删除失败'),
  })

  const importMutation = useMutation({
    mutationFn: (cases: TestCaseCreate[]) => regressionApi.importCases(cases),
    onSuccess: (result) => {
      message.success(`导入完成: ${result.imported}/${result.total}`)
      setImportModal(false)
      setImportText('')
      queryClient.invalidateQueries({ queryKey: ['regression-cases'] })
    },
    onError: () => message.error('导入失败'),
  })

  const handleEdit = (record: TestCase) => {
    setCaseModal({ visible: true, editCase: record })
    form.setFieldsValue({
      ...record,
      expected_ku_ids: record.expected_ku_ids?.join(', ') || '',
      tags: record.tags?.join(', ') || '',
    })
  }

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      const data: TestCaseCreate = {
        ...values,
        expected_ku_ids: values.expected_ku_ids ? values.expected_ku_ids.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
        tags: values.tags ? values.tags.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
        evaluation_criteria: values.evaluation_criteria ? JSON.parse(values.evaluation_criteria) : {},
      }
      
      if (caseModal.editCase) {
        updateMutation.mutate({ id: caseModal.editCase.id, data })
      } else {
        createMutation.mutate(data)
      }
    }).catch(() => {
      message.error('请检查表单')
    })
  }

  const handleImport = () => {
    try {
      const cases = JSON.parse(importText)
      if (!Array.isArray(cases)) {
        message.error('JSON 格式错误，需要数组')
        return
      }
      importMutation.mutate(cases)
    } catch {
      message.error('JSON 解析失败')
    }
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 200 },
    { 
      title: '分类', 
      dataIndex: 'category', 
      key: 'category',
      width: 100,
      render: (cat: string) => {
        const colors: Record<string, string> = { rag: 'blue', llm: 'purple', e2e: 'green' }
        return <Tag color={colors[cat] || 'default'}>{cat.toUpperCase()}</Tag>
      },
    },
    { title: '测试问题', dataIndex: 'query', key: 'query', ellipsis: true },
    { 
      title: '状态', 
      dataIndex: 'is_active', 
      key: 'is_active',
      width: 80,
      render: (active: boolean) => active ? <Badge status="success" text="启用" /> : <Badge status="default" text="禁用" />,
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_: unknown, record: TestCase) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除?" onConfirm={() => deleteMutation.mutate(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Spin spinning={isLoading}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Select
            placeholder="按分类筛选"
            allowClear
            style={{ width: 150 }}
            value={categoryFilter}
            onChange={setCategoryFilter}
          >
            <Select.Option value="rag">RAG 检索</Select.Option>
            <Select.Option value="llm">LLM 生成</Select.Option>
            <Select.Option value="e2e">端到端</Select.Option>
          </Select>
        </Space>
        <Space>
          <Button icon={<UploadOutlined />} onClick={() => setImportModal(true)}>批量导入</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCaseModal({ visible: true, editCase: null })}>新建用例</Button>
        </Space>
      </div>

      <Table dataSource={cases} columns={columns} rowKey="id" pagination={{ pageSize: 10 }} />

      {/* Create/Edit Modal */}
      <Modal
        title={caseModal.editCase ? '编辑测试用例' : '新建测试用例'}
        open={caseModal.visible}
        onCancel={() => { setCaseModal({ visible: false, editCase: null }); form.resetFields() }}
        onOk={handleSubmit}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        width={700}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="用例名称" name="name" rules={[{ required: true }]}>
            <Input placeholder="例如：产品参数查询测试" />
          </Form.Item>
          <Form.Item label="测试分类" name="category" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="rag">RAG 检索测试</Select.Option>
              <Select.Option value="llm">LLM 生成测试</Select.Option>
              <Select.Option value="e2e">端到端测试</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="测试问题" name="query" rules={[{ required: true }]}>
            <TextArea rows={2} placeholder="输入要测试的问题" />
          </Form.Item>
          <Form.Item label="期望检索的 KU ID (逗号分隔)" name="expected_ku_ids">
            <Input placeholder="ku-001, ku-002" />
          </Form.Item>
          <Form.Item label="期望答案 (用于对比)" name="expected_answer">
            <TextArea rows={3} placeholder="期望的标准答案" />
          </Form.Item>
          <Form.Item label="评估标准 (JSON)" name="evaluation_criteria">
            <TextArea rows={2} placeholder='{"关键点": "需包含产品型号", "准确性": "数值需准确"}' />
          </Form.Item>
          <Form.Item label="标签 (逗号分隔)" name="tags">
            <Input placeholder="产品, 参数, 重要" />
          </Form.Item>
          <Form.Item label="启用状态" name="is_active" valuePropName="checked" initialValue={true}>
            <Select>
              <Select.Option value={true}>启用</Select.Option>
              <Select.Option value={false}>禁用</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* Import Modal */}
      <Modal
        title="批量导入测试用例"
        open={importModal}
        onCancel={() => { setImportModal(false); setImportText('') }}
        onOk={handleImport}
        confirmLoading={importMutation.isPending}
        width={600}
      >
        <Alert 
          message="JSON 格式示例" 
          description={`[{"name": "测试1", "category": "e2e", "query": "问题内容", "expected_answer": "期望答案"}]`}
          type="info"
          style={{ marginBottom: 16 }}
        />
        <TextArea 
          rows={10} 
          value={importText} 
          onChange={(e) => setImportText(e.target.value)}
          placeholder="粘贴 JSON 数组..."
        />
      </Modal>
    </Spin>
  )
}

function TestRunsPanel() {
  const queryClient = useQueryClient()
  const [runModal, setRunModal] = useState(false)
  const [selectedRun, setSelectedRun] = useState<TestRun | null>(null)
  const [form] = Form.useForm()

  const { data: stats } = useQuery({
    queryKey: ['regression-stats'],
    queryFn: () => regressionApi.getStats(),
  })

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ['regression-runs'],
    queryFn: () => regressionApi.listRuns({ limit: 20 }),
    refetchInterval: (query) => {
      // Auto-refresh if there's a running test
      const data = query.state.data as TestRun[] | undefined
      return data?.some(r => r.status === 'running') ? 3000 : false
    },
  })

  const { data: evaluatorHealth } = useQuery({
    queryKey: ['evaluator-health'],
    queryFn: () => regressionApi.checkEvaluatorHealth(),
    refetchInterval: 30000,
  })

  const createRunMutation = useMutation({
    mutationFn: (data: { category_filter?: string }) => regressionApi.createRun(data),
    onSuccess: () => {
      message.success('测试已启动')
      setRunModal(false)
      form.resetFields()
      queryClient.invalidateQueries({ queryKey: ['regression-runs'] })
    },
    onError: () => message.error('启动失败'),
  })

  const handleStartRun = () => {
    form.validateFields().then((values) => {
      createRunMutation.mutate({
        category_filter: values.category_filter || undefined,
      })
    })
  }

  const columns = [
    { 
      title: '运行 ID', 
      dataIndex: 'run_id', 
      key: 'run_id',
      render: (id: string) => <Text code>{id}</Text>,
    },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (status: string) => {
        const colors: Record<string, string> = { running: 'processing', completed: 'success', failed: 'error' }
        const texts: Record<string, string> = { running: '运行中', completed: '已完成', failed: '失败' }
        return <Badge status={colors[status] as 'processing' | 'success' | 'error'} text={texts[status] || status} />
      },
    },
    { title: '总用例', dataIndex: 'total_cases', key: 'total_cases' },
    { 
      title: '通过/失败/待复核', 
      key: 'results',
      render: (_: unknown, r: TestRun) => (
        <Space>
          <Text type="success">{r.passed_cases}</Text>
          <Text>/</Text>
          <Text type="danger">{r.failed_cases}</Text>
          <Text>/</Text>
          <Text type="warning">{r.review_cases}</Text>
        </Space>
      ),
    },
    { 
      title: '通过率', 
      dataIndex: 'pass_rate', 
      key: 'pass_rate',
      render: (rate: number) => rate != null ? <Progress percent={Math.round(rate)} size="small" style={{ width: 100 }} /> : '-',
    },
    { 
      title: '开始时间', 
      dataIndex: 'started_at', 
      key: 'started_at',
      render: (t: string) => t ? new Date(t).toLocaleString() : '-',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: TestRun) => (
        <Button type="link" icon={<EyeOutlined />} onClick={() => setSelectedRun(record)}>查看结果</Button>
      ),
    },
  ]

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="总测试用例" value={stats?.total_cases || 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="总运行次数" value={stats?.total_runs || 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="平均通过率" 
              value={stats?.avg_pass_rate || 0} 
              suffix="%" 
              valueStyle={{ color: (stats?.avg_pass_rate || 0) >= 80 ? '#22c55e' : '#ef4444' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="待复核" 
              value={stats?.pending_reviews || 0}
              valueStyle={{ color: (stats?.pending_reviews || 0) > 0 ? '#f59e0b' : undefined }}
            />
          </Card>
        </Col>
      </Row>

      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Text>评估服务状态:</Text>
          {evaluatorHealth?.evaluator_healthy ? (
            <Tag color="success">Ragas 服务正常</Tag>
          ) : (
            <Tag color="warning">Ragas 服务离线 (将使用备用评估)</Tag>
          )}
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => queryClient.invalidateQueries({ queryKey: ['regression-runs'] })}>刷新</Button>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => setRunModal(true)}>开始新测试</Button>
        </Space>
      </div>

      <Spin spinning={isLoading}>
        <Table dataSource={runs} columns={columns} rowKey="id" pagination={{ pageSize: 10 }} />
      </Spin>

      {/* Start Run Modal */}
      <Modal
        title="开始回归测试"
        open={runModal}
        onCancel={() => setRunModal(false)}
        onOk={handleStartRun}
        confirmLoading={createRunMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="测试分类 (可选)" name="category_filter">
            <Select allowClear placeholder="运行所有分类">
              <Select.Option value="rag">仅 RAG 检索测试</Select.Option>
              <Select.Option value="llm">仅 LLM 生成测试</Select.Option>
              <Select.Option value="e2e">仅端到端测试</Select.Option>
            </Select>
          </Form.Item>
          <Alert message="测试将在后台异步执行，您可以随时查看进度" type="info" />
        </Form>
      </Modal>

      {/* Results Modal */}
      <Modal
        title={`测试结果 - ${selectedRun?.run_id || ''}`}
        open={!!selectedRun}
        onCancel={() => setSelectedRun(null)}
        footer={null}
        width={1000}
      >
        {selectedRun && <TestResultsView runId={selectedRun.id} />}
      </Modal>
    </div>
  )
}

function TestResultsView({ runId }: { runId: number }) {
  const queryClient = useQueryClient()
  const [expandedResult, setExpandedResult] = useState<TestResult | null>(null)

  const { data: results = [], isLoading } = useQuery({
    queryKey: ['regression-results', runId],
    queryFn: () => regressionApi.getRunResults(runId),
  })

  const reviewMutation = useMutation({
    mutationFn: ({ resultId, review, comment }: { resultId: number; review: 'pass' | 'fail'; comment?: string }) => 
      regressionApi.submitReview(resultId, { review, comment }),
    onSuccess: () => {
      message.success('复核已提交')
      queryClient.invalidateQueries({ queryKey: ['regression-results', runId] })
      queryClient.invalidateQueries({ queryKey: ['regression-stats'] })
    },
  })

  const columns = [
    { title: '用例', dataIndex: 'case_name', key: 'case_name', ellipsis: true },
    { 
      title: '分类', 
      dataIndex: 'case_category', 
      key: 'case_category',
      render: (cat: string) => cat ? <Tag>{cat.toUpperCase()}</Tag> : '-',
    },
    { 
      title: '检索得分', 
      dataIndex: 'retrieval_score', 
      key: 'retrieval_score',
      render: (score: number) => score != null ? <Progress percent={Math.round(score * 100)} size="small" style={{ width: 80 }} /> : '-',
    },
    { 
      title: '答案得分', 
      dataIndex: 'answer_score', 
      key: 'answer_score',
      render: (score: number) => score != null ? <Progress percent={Math.round(score * 100)} size="small" style={{ width: 80 }} /> : '-',
    },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (status: string) => {
        const colors: Record<string, string> = { pass: 'success', fail: 'error', review: 'warning', pending: 'default' }
        const texts: Record<string, string> = { pass: '通过', fail: '失败', review: '待复核', pending: '等待中' }
        return <Tag color={colors[status]}>{texts[status] || status}</Tag>
      },
    },
    { 
      title: '耗时', 
      dataIndex: 'execution_time_ms', 
      key: 'execution_time_ms',
      render: (ms: number) => ms ? `${ms}ms` : '-',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: TestResult) => (
        <Space>
          <Button type="link" size="small" onClick={() => setExpandedResult(record)}>详情</Button>
          {record.status === 'review' && (
            <>
              <Popconfirm title="确认通过?" onConfirm={() => reviewMutation.mutate({ resultId: record.id, review: 'pass' })}>
                <Button type="link" size="small" icon={<CheckOutlined />} style={{ color: '#22c55e' }}>通过</Button>
              </Popconfirm>
              <Popconfirm title="确认失败?" onConfirm={() => reviewMutation.mutate({ resultId: record.id, review: 'fail' })}>
                <Button type="link" size="small" icon={<CloseOutlined />} danger>失败</Button>
              </Popconfirm>
            </>
          )}
        </Space>
      ),
    },
  ]

  return (
    <Spin spinning={isLoading}>
      <Table dataSource={results} columns={columns} rowKey="id" size="small" pagination={{ pageSize: 10 }} />

      <Modal
        title="测试结果详情"
        open={!!expandedResult}
        onCancel={() => setExpandedResult(null)}
        footer={null}
        width={800}
      >
        {expandedResult && (
          <div>
            <Paragraph><strong>测试问题:</strong> {expandedResult.case_query}</Paragraph>
            <Paragraph><strong>实际答案:</strong></Paragraph>
            <Card size="small" style={{ marginBottom: 16, background: '#f5f5f5' }}>
              <Text>{expandedResult.actual_answer || '(无答案)'}</Text>
            </Card>
            <Row gutter={16}>
              <Col span={12}>
                <Text strong>检索得分: </Text>
                <Progress percent={Math.round((expandedResult.retrieval_score || 0) * 100)} />
              </Col>
              <Col span={12}>
                <Text strong>答案得分: </Text>
                <Progress percent={Math.round((expandedResult.answer_score || 0) * 100)} />
              </Col>
            </Row>
            {expandedResult.llm_evaluation && (
              <Collapse style={{ marginTop: 16 }}>
                <Panel header="Ragas 评估详情" key="1">
                  <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                    {JSON.stringify(expandedResult.llm_evaluation, null, 2)}
                  </pre>
                </Panel>
              </Collapse>
            )}
            {expandedResult.error_message && (
              <Alert message="错误信息" description={expandedResult.error_message} type="error" style={{ marginTop: 16 }} />
            )}
          </div>
        )}
      </Modal>
    </Spin>
  )
}

function ReviewPanel() {
  const queryClient = useQueryClient()
  const [selectedRun, setSelectedRun] = useState<number | null>(null)

  const { data: runs = [] } = useQuery({
    queryKey: ['regression-runs'],
    queryFn: () => regressionApi.listRuns({ status: 'completed', limit: 10 }),
  })

  const { data: results = [], isLoading } = useQuery({
    queryKey: ['regression-review-results', selectedRun],
    queryFn: () => selectedRun ? regressionApi.getRunResults(selectedRun, { manual_review: 'pending' }) : Promise.resolve([]),
    enabled: !!selectedRun,
  })

  const reviewMutation = useMutation({
    mutationFn: ({ resultId, review, comment }: { resultId: number; review: 'pass' | 'fail'; comment?: string }) => 
      regressionApi.submitReview(resultId, { review, comment }),
    onSuccess: () => {
      message.success('复核已提交')
      queryClient.invalidateQueries({ queryKey: ['regression-review-results'] })
      queryClient.invalidateQueries({ queryKey: ['regression-stats'] })
    },
  })

  const columns = [
    { title: '用例', dataIndex: 'case_name', key: 'case_name', width: 200 },
    { title: '测试问题', dataIndex: 'case_query', key: 'case_query', ellipsis: true },
    { 
      title: '检索/答案得分', 
      key: 'scores',
      render: (_: unknown, r: TestResult) => (
        <Space>
          <Tooltip title="检索得分">
            <Tag color="blue">{Math.round((r.retrieval_score || 0) * 100)}%</Tag>
          </Tooltip>
          <Tooltip title="答案得分">
            <Tag color="purple">{Math.round((r.answer_score || 0) * 100)}%</Tag>
          </Tooltip>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: TestResult) => (
        <Space>
          <Button 
            type="primary" 
            size="small" 
            icon={<CheckOutlined />}
            onClick={() => reviewMutation.mutate({ resultId: record.id, review: 'pass' })}
          >
            通过
          </Button>
          <Button 
            danger 
            size="small" 
            icon={<CloseOutlined />}
            onClick={() => reviewMutation.mutate({ resultId: record.id, review: 'fail' })}
          >
            失败
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Text>选择测试运行: </Text>
        <Select
          placeholder="选择要复核的运行"
          style={{ width: 300 }}
          value={selectedRun}
          onChange={setSelectedRun}
        >
          {runs.map((run) => (
            <Select.Option key={run.id} value={run.id}>
              {run.run_id} - {run.review_cases} 条待复核
            </Select.Option>
          ))}
        </Select>
      </div>

      {selectedRun ? (
        <Spin spinning={isLoading}>
          {results.length > 0 ? (
            <Table dataSource={results} columns={columns} rowKey="id" pagination={{ pageSize: 10 }} />
          ) : (
            <Alert message="该运行没有待复核的结果" type="success" />
          )}
        </Spin>
      ) : (
        <Alert message="请选择一个测试运行查看待复核结果" type="info" />
      )}
    </div>
  )
}

function RegressionTest() {
  const [activeSubTab, setActiveSubTab] = useState('cases')
  
  const subTabItems = [
    { key: 'cases', label: '测试用例', children: <TestCasesPanel /> },
    { key: 'runs', label: '测试运行', children: <TestRunsPanel /> },
    { key: 'review', label: '结果复核', children: <ReviewPanel /> },
  ]
  
  return (
    <div>
      <Tabs 
        activeKey={activeSubTab} 
        onChange={setActiveSubTab}
        items={subTabItems}
        type="card"
      />
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

