import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { Card, Menu, Typography, Tabs, Form, Input, Switch, Button, Table, Tag, Space, message, Select, Progress } from 'antd'
import {
  RobotOutlined,
  ApiOutlined,
  SettingOutlined,
  SyncOutlined,
  SafetyOutlined,
  CloudServerOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'

const { Title, Text } = Typography

// Mock data
const mockLLMProviders = [
  { id: 1, provider_code: 'qwen', provider_name: '阿里云百炼 Qwen', api_base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', is_active: true, is_default: true, has_api_key: true },
  { id: 2, provider_code: 'openai', provider_name: 'OpenAI', api_base_url: 'https://api.openai.com/v1', is_active: true, is_default: false, has_api_key: false },
]

const mockModelAssignments = [
  { use_case: 'chat', display: '对话生成', model: 'qwen-max', fallback: 'qwen-plus' },
  { use_case: 'expand', display: '内容扩展', model: 'qwen-plus', fallback: 'qwen-turbo' },
  { use_case: 'summary', display: '对话摘要', model: 'qwen-long', fallback: 'qwen-plus' },
  { use_case: 'intent', display: '意图识别', model: 'qwen-turbo', fallback: 'qwen-max' },
  { use_case: 'embedding', display: '文本嵌入', model: 'text-embedding-v3', fallback: '-' },
  { use_case: 'vision', display: '多模态识别', model: 'qwen-vl-max', fallback: '-' },
]

const mockIntegrations = [
  { name: 'OpenSearch', status: 'connected', url: 'http://opensearch:9200' },
  { name: 'MinIO', status: 'connected', url: 'minio:9000' },
  { name: 'PostgreSQL', status: 'connected', url: 'postgres:5432' },
  { name: 'Redis', status: 'connected', url: 'redis:6379' },
  { name: 'Neo4j', status: 'connected', url: 'neo4j:7687' },
  { name: 'Langfuse', status: 'connected', url: 'langfuse:3000' },
]

const mockFeatures = [
  { key: 'enable_vision', name: '多模态识别', description: '图片/PDF表格识别', enabled: true },
  { key: 'enable_knowledge_graph', name: '知识图谱', description: '实体关系抽取', enabled: true },
  { key: 'enable_recommendation', name: '智能推荐', description: '基于历史的材料推荐', enabled: true },
  { key: 'enable_dialogue_summary', name: '对话摘要', description: '长对话自动总结', enabled: true },
  { key: 'enable_calculation', name: '计算引擎', description: '参数计算和推理', enabled: true },
  { key: 'enable_contribution', name: '用户贡献', description: '允许用户上传材料', enabled: true },
  { key: 'enable_feedback_optimization', name: '反馈优化', description: '基于反馈优化Prompt', enabled: true },
]

const mockConfigSync = [
  { config_key: 'llm.default_temperature', env_var: 'LLM_TEMPERATURE', env_value: '0.7', db_value: '0.8', source: 'database', in_sync: false },
  { config_key: 'llm.default_max_tokens', env_var: 'LLM_MAX_TOKENS', env_value: '2048', db_value: '2048', source: 'env', in_sync: true },
  { config_key: 'search.default_top_k', env_var: null, env_value: null, db_value: '10', source: 'database', in_sync: true },
]

function LLMSettings() {
  return (
    <div>
      <Title level={4}>LLM 配置</Title>
      
      <Card title="提供商" style={{ marginBottom: 16 }}>
        <Table
          dataSource={mockLLMProviders}
          columns={[
            { title: '名称', dataIndex: 'provider_name', key: 'provider_name' },
            { title: 'API Base', dataIndex: 'api_base_url', key: 'api_base_url', ellipsis: true },
            {
              title: 'API Key',
              dataIndex: 'has_api_key',
              key: 'has_api_key',
              render: (has: boolean) => has ? <Tag color="green">已配置</Tag> : <Tag color="red">未配置</Tag>,
            },
            {
              title: '状态',
              key: 'status',
              render: (_: unknown, record: typeof mockLLMProviders[0]) => (
                <Space>
                  {record.is_active && <Tag color="green">启用</Tag>}
                  {record.is_default && <Tag color="blue">默认</Tag>}
                </Space>
              ),
            },
            {
              title: '操作',
              key: 'actions',
              render: () => (
                <Space>
                  <Button type="link" size="small">编辑</Button>
                  <Button type="link" size="small">测试连接</Button>
                </Space>
              ),
            },
          ]}
          rowKey="id"
          pagination={false}
        />
      </Card>
      
      <Card title="模型场景分配">
        <Table
          dataSource={mockModelAssignments}
          columns={[
            { title: '使用场景', dataIndex: 'display', key: 'display' },
            { title: '当前模型', dataIndex: 'model', key: 'model', render: (m: string) => <Tag color="blue">{m}</Tag> },
            { title: '备用模型', dataIndex: 'fallback', key: 'fallback', render: (m: string) => m !== '-' ? <Tag>{m}</Tag> : '-' },
            {
              title: '操作',
              key: 'actions',
              render: () => <Button type="link" size="small">修改</Button>,
            },
          ]}
          rowKey="use_case"
          pagination={false}
        />
      </Card>
      
      <Card title="通用参数" style={{ marginTop: 16 }}>
        <Form layout="inline">
          <Form.Item label="温度">
            <Input defaultValue="0.7" style={{ width: 80 }} />
          </Form.Item>
          <Form.Item label="最大 Token">
            <Input defaultValue="2048" style={{ width: 100 }} />
          </Form.Item>
          <Form.Item label="请求超时(秒)">
            <Input defaultValue="60" style={{ width: 80 }} />
          </Form.Item>
          <Form.Item label="重试次数">
            <Input defaultValue="3" style={{ width: 60 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary">保存</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

function IntegrationSettings() {
  return (
    <div>
      <Title level={4}>集成服务</Title>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        {mockIntegrations.map((integration) => (
          <Card key={integration.name} size="small">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <Text strong>{integration.name}</Text>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>{integration.url}</Text>
              </div>
              <CheckCircleOutlined style={{ color: '#22c55e', fontSize: 20 }} />
            </div>
            <Button type="link" size="small" style={{ padding: 0, marginTop: 8 }}>测试连接</Button>
          </Card>
        ))}
      </div>
    </div>
  )
}

function FeatureSettings() {
  return (
    <div>
      <Title level={4}>功能开关</Title>
      
      <Card>
        {mockFeatures.map((feature) => (
          <div
            key={feature.key}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 0',
              borderBottom: '1px solid #334155',
            }}
          >
            <div>
              <Text strong>{feature.name}</Text>
              <br />
              <Text type="secondary" style={{ fontSize: 12 }}>{feature.description}</Text>
            </div>
            <Switch defaultChecked={feature.enabled} />
          </div>
        ))}
      </Card>
    </div>
  )
}

function ConfigSyncSettings() {
  return (
    <div>
      <Title level={4}>配置同步</Title>
      
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <Text strong>配置同步状态</Text>
            <br />
            <Text type="secondary">最近同步: 2024-01-20 10:30:15</Text>
          </div>
          <Space>
            <Button type="primary" icon={<SyncOutlined />} onClick={() => message.success('同步完成')}>
              立即同步
            </Button>
            <Button>导出 .env</Button>
            <Button>导入</Button>
          </Space>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          <Card size="small">
            <Text type="secondary">来源: .env</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>12</div>
          </Card>
          <Card size="small">
            <Text type="secondary">来源: 数据库</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>45</div>
          </Card>
          <Card size="small">
            <Text type="secondary">已覆盖</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#eab308' }}>3</div>
          </Card>
          <Card size="small">
            <Text type="secondary">未同步</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#ef4444' }}>2</div>
          </Card>
        </div>
      </Card>
      
      <Card title="配置对比">
        <Table
          dataSource={mockConfigSync}
          columns={[
            { title: '配置项', dataIndex: 'config_key', key: 'config_key' },
            { title: '环境变量', dataIndex: 'env_var', key: 'env_var', render: (v: string | null) => v || '-' },
            { title: '.env 值', dataIndex: 'env_value', key: 'env_value', render: (v: string | null) => v || '-' },
            { title: '数据库值', dataIndex: 'db_value', key: 'db_value' },
            {
              title: '来源',
              dataIndex: 'source',
              key: 'source',
              render: (source: string) => (
                <Tag color={source === 'database' ? 'blue' : 'green'}>{source === 'database' ? 'DB' : 'ENV'}</Tag>
              ),
            },
            {
              title: '同步状态',
              dataIndex: 'in_sync',
              key: 'in_sync',
              render: (inSync: boolean) => inSync ? (
                <CheckCircleOutlined style={{ color: '#22c55e' }} />
              ) : (
                <ExclamationCircleOutlined style={{ color: '#eab308' }} />
              ),
            },
          ]}
          rowKey="config_key"
          pagination={false}
        />
      </Card>
      
      <div style={{ marginTop: 16, padding: 16, background: 'rgba(234, 179, 8, 0.1)', borderRadius: 8, border: '1px solid rgba(234, 179, 8, 0.3)' }}>
        <Text type="warning">
          ⚠️ 提示: 启动必需配置（数据库连接等）不可在界面修改，请直接编辑 .env 文件后重启服务。
        </Text>
      </div>
    </div>
  )
}

export default function Settings() {
  const navigate = useNavigate()
  const location = useLocation()
  
  const currentTab = location.pathname.split('/').pop() || 'llm'
  
  const tabItems = [
    { key: 'llm', label: 'LLM 配置', icon: <RobotOutlined />, children: <LLMSettings /> },
    { key: 'integrations', label: '集成服务', icon: <ApiOutlined />, children: <IntegrationSettings /> },
    { key: 'features', label: '功能开关', icon: <SettingOutlined />, children: <FeatureSettings /> },
    { key: 'sync', label: '配置同步', icon: <SyncOutlined />, children: <ConfigSyncSettings /> },
  ]
  
  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>系统设置</Title>
      
      <Card>
        <Tabs
          activeKey={currentTab}
          onChange={(key) => navigate(`/settings/${key}`)}
          items={tabItems}
        />
      </Card>
    </div>
  )
}

