import { useState } from 'react'
import { Card, Tabs, Table, Button, Space, Tag, Modal, Form, Input, Select, message, Typography } from 'antd'
import { PlusOutlined, EditOutlined, HistoryOutlined, PlayCircleOutlined } from '@ant-design/icons'

const { Title } = Typography
const { TextArea } = Input

// Mock data
const mockScenarios = [
  { id: 'param_query', name: '参数查询', description: '查询产品技术参数', icon: '📊', is_active: true, sort_order: 1 },
  { id: 'case_search', name: '案例检索', description: '搜索客户成功案例', icon: '📋', is_active: true, sort_order: 2 },
  { id: 'quote_calc', name: '报价测算', description: '计算产品报价', icon: '💰', is_active: true, sort_order: 3 },
  { id: 'solution_gen', name: '方案生成', description: '生成解决方案', icon: '📝', is_active: true, sort_order: 4 },
  { id: 'competitor', name: '竞品对比', description: '对比竞争产品', icon: '⚔️', is_active: false, sort_order: 5 },
]

const mockPrompts = [
  { id: 1, name: '系统 Prompt (通用)', type: 'system', scenario_id: null, version: 3, is_active: true },
  { id: 2, name: '参数查询 Prompt', type: 'response', scenario_id: 'param_query', version: 2, is_active: true },
  { id: 3, name: '案例检索 Prompt', type: 'response', scenario_id: 'case_search', version: 1, is_active: true },
  { id: 4, name: '意图识别 Prompt', type: 'intent', scenario_id: null, version: 5, is_active: true },
]

const mockKUTypes = [
  { type_code: 'core.product_feature', category: 'product', display_name: '产品功能说明', merge_strategy: 'smart_merge' },
  { type_code: 'core.tech_spec', category: 'product', display_name: '技术规格', merge_strategy: 'smart_merge' },
  { type_code: 'case.customer_story', category: 'case', display_name: '客户案例', merge_strategy: 'independent' },
  { type_code: 'quote.pricebook', category: 'quote', display_name: '报价单', merge_strategy: 'independent' },
]

export default function Config() {
  const [promptModal, setPromptModal] = useState<{ visible: boolean; item: typeof mockPrompts[0] | null }>({
    visible: false,
    item: null,
  })
  const [form] = Form.useForm()
  
  const scenarioColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id' },
    { title: '图标', dataIndex: 'icon', key: 'icon' },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description' },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'default'}>{active ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      render: () => (
        <Space>
          <Button type="link" icon={<EditOutlined />}>编辑</Button>
        </Space>
      ),
    },
  ]
  
  const promptColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => {
        const colors: Record<string, string> = {
          system: 'purple',
          response: 'blue',
          intent: 'green',
          summary: 'orange',
        }
        return <Tag color={colors[type] || 'default'}>{type}</Tag>
      },
    },
    { title: '场景', dataIndex: 'scenario_id', key: 'scenario_id', render: (id: string | null) => id || '通用' },
    { title: '版本', dataIndex: 'version', key: 'version', render: (v: number) => `v${v}` },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'default'}>{active ? '活跃' : '禁用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: typeof mockPrompts[0]) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => setPromptModal({ visible: true, item: record })}>
            编辑
          </Button>
          <Button type="link" icon={<HistoryOutlined />}>历史</Button>
          <Button type="link" icon={<PlayCircleOutlined />}>测试</Button>
        </Space>
      ),
    },
  ]
  
  const kuTypeColumns = [
    { title: '类型代码', dataIndex: 'type_code', key: 'type_code' },
    { title: '分类', dataIndex: 'category', key: 'category' },
    { title: '显示名称', dataIndex: 'display_name', key: 'display_name' },
    {
      title: '合并策略',
      dataIndex: 'merge_strategy',
      key: 'merge_strategy',
      render: (strategy: string) => {
        const colors: Record<string, string> = {
          smart_merge: 'blue',
          independent: 'green',
          append: 'orange',
        }
        return <Tag color={colors[strategy]}>{strategy}</Tag>
      },
    },
  ]
  
  const tabItems = [
    {
      key: 'scenarios',
      label: '场景配置',
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button type="primary" icon={<PlusOutlined />}>新建场景</Button>
          </div>
          <Table dataSource={mockScenarios} columns={scenarioColumns} rowKey="id" />
        </div>
      ),
    },
    {
      key: 'prompts',
      label: 'Prompt 模板',
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button type="primary" icon={<PlusOutlined />}>新建 Prompt</Button>
          </div>
          <Table dataSource={mockPrompts} columns={promptColumns} rowKey="id" />
        </div>
      ),
    },
    {
      key: 'ku-types',
      label: 'KU 类型',
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button type="primary" icon={<PlusOutlined />}>新建类型</Button>
          </div>
          <Table dataSource={mockKUTypes} columns={kuTypeColumns} rowKey="type_code" />
        </div>
      ),
    },
  ]
  
  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>配置管理</Title>
      
      <Card>
        <Tabs items={tabItems} />
      </Card>
      
      {/* Prompt Edit Modal */}
      <Modal
        title={promptModal.item ? `编辑: ${promptModal.item.name}` : '新建 Prompt'}
        open={promptModal.visible}
        onCancel={() => setPromptModal({ visible: false, item: null })}
        onOk={() => {
          message.success('保存成功')
          setPromptModal({ visible: false, item: null })
        }}
        width={800}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="名称" name="name" rules={[{ required: true }]}>
            <Input defaultValue={promptModal.item?.name} />
          </Form.Item>
          
          <Form.Item label="类型" name="type" rules={[{ required: true }]}>
            <Select defaultValue={promptModal.item?.type}>
              <Select.Option value="system">System</Select.Option>
              <Select.Option value="response">Response</Select.Option>
              <Select.Option value="intent">Intent</Select.Option>
              <Select.Option value="summary">Summary</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="场景" name="scenario_id">
            <Select defaultValue={promptModal.item?.scenario_id} allowClear placeholder="通用">
              {mockScenarios.map((s) => (
                <Select.Option key={s.id} value={s.id}>{s.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item label="模板内容" name="template" rules={[{ required: true }]}>
            <TextArea rows={10} placeholder="输入 Prompt 模板..." />
          </Form.Item>
          
          <Form.Item label="变更原因" name="change_reason">
            <Input placeholder="说明本次修改原因（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

