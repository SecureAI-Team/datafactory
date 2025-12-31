import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Card, Typography, Tabs, Form, Input, Switch, Button, Table, Tag, Space, message, Spin, Modal, Select, InputNumber } from 'antd'
import {
  RobotOutlined,
  ApiOutlined,
  SettingOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  PlusOutlined,
  EditOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi, LLMProvider, LLMModel, ModelAssignment, IntegrationStatus, FeatureFlag, SystemConfig } from '../api'

const { Title, Text } = Typography
const { TextArea } = Input

// ==================== LLM Settings ====================
function LLMSettings() {
  const queryClient = useQueryClient()
  
  // Modal states
  const [providerModal, setProviderModal] = useState<{ visible: boolean; item: LLMProvider | null; isNew: boolean }>({
    visible: false,
    item: null,
    isNew: false,
  })
  const [modelModal, setModelModal] = useState<{ visible: boolean; item: LLMModel | null; isNew: boolean }>({
    visible: false,
    item: null,
    isNew: false,
  })
  const [assignmentModal, setAssignmentModal] = useState<{ visible: boolean; item: ModelAssignment | null }>({
    visible: false,
    item: null,
  })
  const [generalParamsModal, setGeneralParamsModal] = useState(false)
  
  // Forms
  const [providerForm] = Form.useForm()
  const [modelForm] = Form.useForm()
  const [assignmentForm] = Form.useForm()
  const [generalParamsForm] = Form.useForm()
  
  // Queries
  const { data: providersData, isLoading: loadingProviders } = useQuery({
    queryKey: ['settings-llm-providers'],
    queryFn: () => settingsApi.getProviders(),
  })
  
  const { data: modelsData, isLoading: loadingModels } = useQuery({
    queryKey: ['settings-llm-models'],
    queryFn: () => settingsApi.getModels(),
  })
  
  const { data: assignmentsData, isLoading: loadingAssignments } = useQuery({
    queryKey: ['settings-llm-assignments'],
    queryFn: () => settingsApi.getAssignments(),
  })
  
  // Mutations
  const testProviderMutation = useMutation({
    mutationFn: (providerId: number) => settingsApi.testProvider(providerId),
    onSuccess: (data) => {
      if (data.success) {
        message.success(`连接测试成功: ${data.message}`)
      } else {
        message.error(`连接测试失败: ${data.message}`)
      }
    },
    onError: () => message.error('测试请求失败'),
  })
  
  const createProviderMutation = useMutation({
    mutationFn: settingsApi.createProvider,
    onSuccess: () => {
      message.success('提供商创建成功')
      queryClient.invalidateQueries({ queryKey: ['settings-llm-providers'] })
      setProviderModal({ visible: false, item: null, isNew: false })
      providerForm.resetFields()
    },
    onError: () => message.error('创建失败'),
  })
  
  const updateProviderMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<LLMProvider> }) => 
      settingsApi.updateProvider(id, data),
    onSuccess: () => {
      message.success('提供商更新成功')
      queryClient.invalidateQueries({ queryKey: ['settings-llm-providers'] })
      setProviderModal({ visible: false, item: null, isNew: false })
    },
    onError: () => message.error('更新失败'),
  })
  
  const updateModelMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<LLMModel> }) =>
      settingsApi.updateModel(id, data),
    onSuccess: () => {
      message.success('模型更新成功')
      queryClient.invalidateQueries({ queryKey: ['settings-llm-models'] })
      setModelModal({ visible: false, item: null, isNew: false })
    },
    onError: () => message.error('更新失败'),
  })
  
  const updateAssignmentMutation = useMutation({
    mutationFn: ({ useCase, data }: { useCase: string; data: Partial<ModelAssignment> }) =>
      settingsApi.updateAssignment(useCase, data),
    onSuccess: () => {
      message.success('分配更新成功')
      queryClient.invalidateQueries({ queryKey: ['settings-llm-assignments'] })
      setAssignmentModal({ visible: false, item: null })
    },
    onError: () => message.error('更新失败'),
  })
  
  // Form effects
  useEffect(() => {
    if (providerModal.item && !providerModal.isNew) {
      providerForm.setFieldsValue({
        ...providerModal.item,
        api_key: '', // Don't show actual API key
      })
    } else if (providerModal.isNew) {
      providerForm.resetFields()
      providerForm.setFieldsValue({ is_active: true, is_default: false })
    }
  }, [providerModal, providerForm])
  
  useEffect(() => {
    if (modelModal.item && !modelModal.isNew) {
      // Exclude complex object fields to prevent React render errors
      const { config: _config, capabilities: _capabilities, ...formValues } = modelModal.item as Record<string, unknown>
      modelForm.setFieldsValue(formValues)
    } else if (modelModal.isNew) {
      modelForm.resetFields()
      modelForm.setFieldsValue({ is_active: true, is_default: false })
    }
  }, [modelModal, modelForm])
  
  useEffect(() => {
    if (assignmentModal.item) {
      // Exclude config_override to prevent React render errors
      const { config_override: _config_override, ...formValues } = assignmentModal.item as Record<string, unknown>
      assignmentForm.setFieldsValue(formValues)
    }
  }, [assignmentModal, assignmentForm])
  
  const handleSaveProvider = () => {
    providerForm.validateFields().then((values) => {
      // Don't send empty api_key
      if (values.api_key === '') {
        delete values.api_key
      }
      if (providerModal.isNew) {
        createProviderMutation.mutate(values)
      } else if (providerModal.item) {
        updateProviderMutation.mutate({ id: providerModal.item.id, data: values })
      }
    })
  }
  
  const handleSaveModel = () => {
    modelForm.validateFields().then((values) => {
      if (modelModal.item) {
        updateModelMutation.mutate({ id: modelModal.item.id, data: values })
      }
    })
  }
  
  const handleSaveAssignment = () => {
    assignmentForm.validateFields().then((values) => {
      if (assignmentModal.item) {
        updateAssignmentMutation.mutate({ useCase: assignmentModal.item.use_case, data: values })
      }
    })
  }
  
  const saveGeneralParamsMutation = useMutation({
    mutationFn: settingsApi.updateLLMGeneralParams,
    onSuccess: () => {
      message.success('通用参数已保存')
      setGeneralParamsModal(false)
    },
    onError: () => message.error('保存失败'),
  })
  
  const handleSaveGeneralParams = () => {
    generalParamsForm.validateFields().then((values) => {
      saveGeneralParamsMutation.mutate(values)
    })
  }
  
  const useCaseLabels: Record<string, string> = {
    chat: '对话生成',
    expand: '内容扩展',
    summary: '对话摘要',
    intent: '意图识别',
    embedding: '文本嵌入',
    vision: '多模态识别',
  }
  
  const getModelCode = (modelId: number | undefined): string => {
    if (!modelId || !modelsData?.models) return '-'
    const model = modelsData.models.find(m => m.id === modelId)
    return model?.model_code || '-'
  }
  
  const getProviderName = (providerId: number): string => {
    const provider = providersData?.providers.find(p => p.id === providerId)
    return provider?.provider_name || '-'
  }
  
  return (
    <div>
      <Title level={4}>LLM 配置</Title>
      
      {/* Providers */}
      <Card 
        title="提供商" 
        style={{ marginBottom: 16 }}
        extra={
          <Button 
            type="primary" 
            icon={<PlusOutlined />}
            onClick={() => setProviderModal({ visible: true, item: null, isNew: true })}
          >
            添加提供商
          </Button>
        }
      >
        <Spin spinning={loadingProviders}>
          <Table
            dataSource={providersData?.providers ?? []}
            columns={[
              { title: '名称', dataIndex: 'provider_name', key: 'provider_name' },
              { title: '代码', dataIndex: 'provider_code', key: 'provider_code' },
              { title: 'API Base', dataIndex: 'api_base_url', key: 'api_base_url', ellipsis: true },
              {
                title: '状态',
                key: 'status',
                render: (_: unknown, record: LLMProvider) => (
                  <Space>
                    {record.is_active && <Tag color="green">启用</Tag>}
                    {record.is_default && <Tag color="blue">默认</Tag>}
                  </Space>
                ),
              },
              {
                title: '操作',
                key: 'actions',
                render: (_: unknown, record: LLMProvider) => (
                  <Space>
                    <Button 
                      type="link" 
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => setProviderModal({ visible: true, item: record, isNew: false })}
                    >
                      编辑
                    </Button>
                    <Button 
                      type="link" 
                      size="small"
                      loading={testProviderMutation.isPending}
                      onClick={() => testProviderMutation.mutate(record.id)}
                    >
                      测试连接
                    </Button>
                  </Space>
                ),
              },
            ]}
            rowKey="id"
            pagination={false}
            locale={{ emptyText: '暂无提供商配置' }}
          />
        </Spin>
      </Card>
      
      {/* Models */}
      <Card title="模型列表" style={{ marginBottom: 16 }}>
        <Spin spinning={loadingModels}>
          <Table
            dataSource={modelsData?.models ?? []}
            columns={[
              { title: '模型名称', dataIndex: 'model_name', key: 'model_name' },
              { title: '模型代码', dataIndex: 'model_code', key: 'model_code' },
              { title: '类型', dataIndex: 'model_type', key: 'model_type', render: (t: string) => <Tag>{t}</Tag> },
              { title: '提供商', dataIndex: 'provider_id', key: 'provider_id', render: getProviderName },
              { title: '上下文窗口', dataIndex: 'context_window', key: 'context_window', render: (v: number) => v ? `${v.toLocaleString()} tokens` : '-' },
              {
                title: '状态',
                key: 'status',
                render: (_: unknown, record: LLMModel) => (
                  <Space>
                    {record.is_active && <Tag color="green">启用</Tag>}
                    {record.is_default && <Tag color="blue">默认</Tag>}
                  </Space>
                ),
              },
              {
                title: '操作',
                key: 'actions',
                render: (_: unknown, record: LLMModel) => (
                  <Button 
                    type="link" 
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => setModelModal({ visible: true, item: record, isNew: false })}
                  >
                    编辑
                  </Button>
                ),
              },
            ]}
            rowKey="id"
            pagination={false}
            locale={{ emptyText: '暂无模型配置' }}
          />
        </Spin>
      </Card>
      
      {/* Assignments */}
      <Card title="模型场景分配" style={{ marginBottom: 16 }}>
        <Spin spinning={loadingAssignments || loadingModels}>
          <Table
            dataSource={assignmentsData?.assignments ?? []}
            columns={[
              { 
                title: '使用场景', 
                dataIndex: 'use_case', 
                key: 'use_case',
                render: (uc: string) => useCaseLabels[uc] || uc
              },
              { 
                title: '当前模型', 
                dataIndex: 'model_id', 
                key: 'model_id', 
                render: (id: number) => <Tag color="blue">{getModelCode(id)}</Tag> 
              },
              { 
                title: '备用模型', 
                dataIndex: 'fallback_model_id', 
                key: 'fallback_model_id', 
                render: (id: number) => id ? <Tag>{getModelCode(id)}</Tag> : '-' 
              },
              {
                title: '操作',
                key: 'actions',
                render: (_: unknown, record: ModelAssignment) => (
                  <Button 
                    type="link" 
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => setAssignmentModal({ visible: true, item: record })}
                  >
                    修改
                  </Button>
                ),
              },
            ]}
            rowKey="use_case"
            pagination={false}
            locale={{ emptyText: '暂无场景分配' }}
          />
        </Spin>
      </Card>
      
      {/* General Params */}
      <Card 
        title="通用参数"
        extra={
          <Button type="primary" onClick={() => setGeneralParamsModal(true)}>
            编辑参数
          </Button>
        }
      >
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          <Card size="small">
            <Text type="secondary">默认温度</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>0.7</div>
          </Card>
          <Card size="small">
            <Text type="secondary">最大 Token</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>2048</div>
          </Card>
          <Card size="small">
            <Text type="secondary">请求超时</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>60s</div>
          </Card>
          <Card size="small">
            <Text type="secondary">重试次数</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>3</div>
          </Card>
        </div>
      </Card>
      
      {/* Provider Edit Modal */}
      <Modal
        title={providerModal.isNew ? '添加 LLM 提供商' : `编辑: ${providerModal.item?.provider_name || ''}`}
        open={providerModal.visible}
        onCancel={() => setProviderModal({ visible: false, item: null, isNew: false })}
        onOk={handleSaveProvider}
        confirmLoading={createProviderMutation.isPending || updateProviderMutation.isPending}
        width={600}
      >
        <Form form={providerForm} layout="vertical">
          <Form.Item 
            label="提供商代码" 
            name="provider_code" 
            rules={[{ required: true, message: '请输入提供商代码' }]}
            extra="如: openai, azure, aliyun, baidu 等"
          >
            <Input disabled={!providerModal.isNew} placeholder="openai" />
          </Form.Item>
          
          <Form.Item 
            label="提供商名称" 
            name="provider_name" 
            rules={[{ required: true, message: '请输入提供商名称' }]}
          >
            <Input placeholder="OpenAI" />
          </Form.Item>
          
          <Form.Item label="API Base URL" name="api_base_url">
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          
          <Form.Item 
            label="API Key" 
            name="api_key" 
            extra={providerModal.item ? '留空则不修改现有 API Key' : ''}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          
          <Space>
            <Form.Item label="启用" name="is_active" valuePropName="checked">
              <Switch />
            </Form.Item>
            
            <Form.Item label="设为默认" name="is_default" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
      
      {/* Model Edit Modal */}
      <Modal
        title={`编辑模型: ${modelModal.item?.model_name || ''}`}
        open={modelModal.visible}
        onCancel={() => setModelModal({ visible: false, item: null, isNew: false })}
        onOk={handleSaveModel}
        confirmLoading={updateModelMutation.isPending}
        width={600}
      >
        <Form form={modelForm} layout="vertical">
          <Form.Item label="模型代码" name="model_code">
            <Input disabled />
          </Form.Item>
          
          <Form.Item 
            label="模型名称" 
            name="model_name" 
            rules={[{ required: true }]}
          >
            <Input placeholder="GPT-4o" />
          </Form.Item>
          
          <Form.Item label="模型类型" name="model_type">
            <Select>
              <Select.Option value="chat">Chat</Select.Option>
              <Select.Option value="embedding">Embedding</Select.Option>
              <Select.Option value="vision">Vision</Select.Option>
              <Select.Option value="audio">Audio</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="上下文窗口" name="context_window">
            <InputNumber style={{ width: '100%' }} placeholder="128000" />
          </Form.Item>
          
          <Form.Item label="最大输出 Token" name="max_output_tokens">
            <InputNumber style={{ width: '100%' }} placeholder="4096" />
          </Form.Item>
          
          <Space>
            <Form.Item label="启用" name="is_active" valuePropName="checked">
              <Switch />
            </Form.Item>
            
            <Form.Item label="设为默认" name="is_default" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
      
      {/* Assignment Edit Modal */}
      <Modal
        title={`修改场景分配: ${assignmentModal.item ? useCaseLabels[assignmentModal.item.use_case] || assignmentModal.item.use_case : ''}`}
        open={assignmentModal.visible}
        onCancel={() => setAssignmentModal({ visible: false, item: null })}
        onOk={handleSaveAssignment}
        confirmLoading={updateAssignmentMutation.isPending}
        width={500}
      >
        <Form form={assignmentForm} layout="vertical">
          <Form.Item 
            label="主模型" 
            name="model_id" 
            rules={[{ required: true, message: '请选择主模型' }]}
          >
            <Select placeholder="选择主模型">
              {modelsData?.models.map(m => (
                <Select.Option key={m.id} value={m.id}>
                  {m.model_name} ({m.model_code})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item label="备用模型" name="fallback_model_id">
            <Select allowClear placeholder="选择备用模型（可选）">
              {modelsData?.models.map(m => (
                <Select.Option key={m.id} value={m.id}>
                  {m.model_name} ({m.model_code})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
      
      {/* General Params Modal */}
      <Modal
        title="编辑通用参数"
        open={generalParamsModal}
        onCancel={() => setGeneralParamsModal(false)}
        onOk={handleSaveGeneralParams}
        width={500}
      >
        <Form form={generalParamsForm} layout="vertical" initialValues={{ temperature: 0.7, max_tokens: 2048, timeout: 60, retries: 3 }}>
          <Form.Item label="默认温度" name="temperature">
            <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
          </Form.Item>
          
          <Form.Item label="最大输出 Token" name="max_tokens">
            <InputNumber min={1} max={32000} style={{ width: '100%' }} />
          </Form.Item>
          
          <Form.Item label="请求超时 (秒)" name="timeout">
            <InputNumber min={1} max={300} style={{ width: '100%' }} />
          </Form.Item>
          
          <Form.Item label="重试次数" name="retries">
            <InputNumber min={0} max={10} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// ==================== Integration Settings ====================
function IntegrationSettings() {
  const queryClient = useQueryClient()
  
  const { data: integrationsData, isLoading } = useQuery({
    queryKey: ['settings-integrations'],
    queryFn: () => settingsApi.getIntegrations(),
  })
  
  const testMutation = useMutation({
    mutationFn: (service: string) => settingsApi.testIntegration(service),
    onSuccess: (data) => {
      if (data.status === 'connected') {
        message.success(`${data.name} 连接成功`)
      } else {
        message.error(`${data.name} 连接失败: ${data.message}`)
      }
      queryClient.invalidateQueries({ queryKey: ['settings-integrations'] })
    },
    onError: () => message.error('测试请求失败'),
  })
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'connected':
        return <CheckCircleOutlined style={{ color: '#22c55e', fontSize: 20 }} />
      case 'disconnected':
        return <CloseCircleOutlined style={{ color: '#ef4444', fontSize: 20 }} />
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#eab308', fontSize: 20 }} />
      default:
        return <ExclamationCircleOutlined style={{ color: '#64748b', fontSize: 20 }} />
    }
  }
  
  return (
    <div>
      <Title level={4}>集成服务</Title>
      
      <Spin spinning={isLoading}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
          {(integrationsData?.integrations ?? []).map((integration: IntegrationStatus) => (
            <Card key={integration.name} size="small">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <Text strong>{integration.name}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {integration.message || integration.status}
                  </Text>
                  {integration.last_checked && (
                    <>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        上次检查: {new Date(integration.last_checked).toLocaleString()}
                      </Text>
                    </>
                  )}
                </div>
                {getStatusIcon(integration.status)}
              </div>
              <Button 
                type="link" 
                size="small" 
                style={{ padding: 0, marginTop: 8 }}
                loading={testMutation.isPending}
                onClick={() => testMutation.mutate(integration.name.toLowerCase())}
              >
                测试连接
              </Button>
            </Card>
          ))}
        </div>
      </Spin>
      
      {(!integrationsData?.integrations || integrationsData.integrations.length === 0) && !isLoading && (
        <Card>
          <Text type="secondary">暂无集成服务配置</Text>
        </Card>
      )}
    </div>
  )
}

// ==================== Feature Settings ====================
function FeatureSettings() {
  const queryClient = useQueryClient()
  
  const { data: featuresData, isLoading } = useQuery({
    queryKey: ['settings-features'],
    queryFn: () => settingsApi.getFeatures(),
  })
  
  const toggleMutation = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) => 
      settingsApi.toggleFeature(key, enabled),
    onSuccess: (data) => {
      message.success(`${data.key} ${data.enabled ? '已启用' : '已禁用'}`)
      queryClient.invalidateQueries({ queryKey: ['settings-features'] })
    },
    onError: () => message.error('操作失败'),
  })
  
  return (
    <div>
      <Title level={4}>功能开关</Title>
      
      <Card>
        <Spin spinning={isLoading}>
          {(featuresData?.features ?? []).map((feature: FeatureFlag) => (
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
                <Text strong>{feature.key}</Text>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>{feature.description || '-'}</Text>
              </div>
              <Switch 
                checked={feature.enabled} 
                loading={toggleMutation.isPending}
                onChange={(checked) => toggleMutation.mutate({ key: feature.key, enabled: checked })}
              />
            </div>
          ))}
          {(!featuresData?.features || featuresData.features.length === 0) && !isLoading && (
            <Text type="secondary">暂无功能开关配置</Text>
          )}
        </Spin>
      </Card>
    </div>
  )
}

// ==================== Config Sync Settings ====================
interface ConfigComparison {
  config_key: string
  env_var: string
  env_value?: string
  db_value?: string
  source: string
  in_sync: boolean
}

function ConfigSyncSettings() {
  const queryClient = useQueryClient()
  const [exportModalVisible, setExportModalVisible] = useState(false)
  const [exportContent, setExportContent] = useState('')
  
  // Fetch system configs for comparison
  const { data: systemConfigsData, isLoading: loadingConfigs } = useQuery({
    queryKey: ['settings-system-configs'],
    queryFn: () => settingsApi.getSystemConfigs(),
  })
  
  // Create comparison data from system configs
  const comparisons: ConfigComparison[] = (systemConfigsData?.configs ?? []).map((cfg: SystemConfig) => ({
    config_key: cfg.config_key,
    env_var: cfg.config_key.toUpperCase().replace(/\./g, '_'),
    env_value: cfg.default_value,
    db_value: cfg.config_value,
    source: cfg.config_value ? 'db' : 'env',
    in_sync: cfg.config_value === cfg.default_value || (!cfg.config_value && !cfg.default_value),
  }))
  
  const configStats = {
    env: comparisons.filter(c => c.env_value).length,
    db: comparisons.filter(c => c.db_value).length,
    overwritten: comparisons.filter(c => c.source === 'db' && !c.in_sync).length,
    not_synced: comparisons.filter(c => c.source === 'env' && !c.in_sync).length,
  }
  
  const syncMutation = useMutation({
    mutationFn: settingsApi.syncConfigs,
    onSuccess: (data) => {
      message.success(data.message || `已同步 ${data.synced} 项配置`)
      queryClient.invalidateQueries({ queryKey: ['settings-system-configs'] })
    },
    onError: () => message.error('同步失败'),
  })
  
  const handleSync = () => {
    syncMutation.mutate()
  }
  
  const handleExport = () => {
    // Generate .env format from configs
    const envContent = comparisons
      .filter(c => c.db_value || c.env_value)
      .map(c => `${c.env_var}=${c.db_value || c.env_value || ''}`)
      .join('\n')
    setExportContent(envContent || '# No configurations to export')
    setExportModalVisible(true)
  }
  
  const handleCopyExport = () => {
    navigator.clipboard.writeText(exportContent)
    message.success('已复制到剪贴板')
  }
  
  return (
    <div>
      <Title level={4}>配置同步</Title>
      
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <Text strong>配置同步状态</Text>
            <br />
            <Text type="secondary">管理环境变量与数据库配置的同步</Text>
          </div>
          <Space>
            <Button type="primary" icon={<SyncOutlined />} onClick={handleSync}>
              立即同步
            </Button>
            <Button onClick={handleExport}>导出 .env</Button>
          </Space>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          <Card size="small">
            <Text type="secondary">来源: .env</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>{configStats.env}</div>
          </Card>
          <Card size="small">
            <Text type="secondary">来源: 数据库</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>{configStats.db}</div>
          </Card>
          <Card size="small">
            <Text type="secondary">已覆盖</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#eab308' }}>{configStats.overwritten}</div>
          </Card>
          <Card size="small">
            <Text type="secondary">未同步</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#ef4444' }}>{configStats.not_synced}</div>
          </Card>
        </div>
      </Card>
      
      <Card title="配置对比">
        <Spin spinning={loadingConfigs}>
          <Table
            dataSource={comparisons}
            columns={[
              { title: '配置项', dataIndex: 'config_key', key: 'config_key' },
              { title: '环境变量', dataIndex: 'env_var', key: 'env_var' },
              { title: '.env 值', dataIndex: 'env_value', key: 'env_value', ellipsis: true, render: (v: string) => v || '-' },
              { title: '数据库值', dataIndex: 'db_value', key: 'db_value', ellipsis: true, render: (v: string) => v || '-' },
              { title: '来源', dataIndex: 'source', key: 'source', render: (s: string) => <Tag color={s === 'db' ? 'blue' : 'green'}>{s}</Tag> },
              { 
                title: '同步状态', 
                dataIndex: 'in_sync', 
                key: 'in_sync', 
                render: (inSync: boolean) => (
                  <Tag color={inSync ? 'green' : 'orange'}>{inSync ? '一致' : '不一致'}</Tag>
                )
              },
            ]}
            rowKey="config_key"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: '暂无配置项' }}
          />
        </Spin>
      </Card>
      
      <div style={{ marginTop: 16, padding: 16, background: 'rgba(234, 179, 8, 0.1)', borderRadius: 8, border: '1px solid rgba(234, 179, 8, 0.3)' }}>
        <Text type="warning">
          ⚠️ 提示: 启动必需配置（数据库连接等）不可在界面修改，请直接编辑 .env 文件后重启服务。
        </Text>
      </div>
      
      {/* Export Modal */}
      <Modal
        title="导出配置 (.env 格式)"
        open={exportModalVisible}
        onCancel={() => setExportModalVisible(false)}
        footer={[
          <Button key="copy" onClick={handleCopyExport}>复制到剪贴板</Button>,
          <Button key="close" type="primary" onClick={() => setExportModalVisible(false)}>关闭</Button>,
        ]}
        width={700}
      >
        <TextArea 
          value={exportContent} 
          rows={15} 
          readOnly 
          style={{ fontFamily: 'monospace', fontSize: 12 }}
        />
      </Modal>
    </div>
  )
}

// ==================== Main Settings Component ====================
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
