import React, { useState, useEffect } from 'react'
import { Card, Tabs, Table, Button, Space, Tag, Modal, Form, Input, Select, message, Typography, Spin, List, Switch } from 'antd'
import { PlusOutlined, EditOutlined, HistoryOutlined, PlayCircleOutlined, RollbackOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, Scenario, PromptTemplate, KUType } from '../api'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

interface PromptHistoryItem {
  id: number
  version: number
  template: string
  changed_by?: number
  change_reason?: string
  created_at: string
}

export default function Config() {
  const queryClient = useQueryClient()
  
  // Modal states
  const [promptModal, setPromptModal] = useState<{ visible: boolean; item: PromptTemplate | null; isNew: boolean }>({
    visible: false,
    item: null,
    isNew: false,
  })
  const [scenarioModal, setScenarioModal] = useState<{ visible: boolean; item: Scenario | null; isNew: boolean }>({
    visible: false,
    item: null,
    isNew: false,
  })
  const [kuTypeModal, setKuTypeModal] = useState<{ visible: boolean; item: KUType | null; isNew: boolean }>({
    visible: false,
    item: null,
    isNew: false,
  })
  const [historyModal, setHistoryModal] = useState<{ visible: boolean; promptId: number | null; promptName: string }>({
    visible: false,
    promptId: null,
    promptName: '',
  })
  const [testModal, setTestModal] = useState<{ visible: boolean; prompt: PromptTemplate | null }>({
    visible: false,
    prompt: null,
  })
  
  // Forms
  const [promptForm] = Form.useForm()
  const [scenarioForm] = Form.useForm()
  const [kuTypeForm] = Form.useForm()
  const [testInput, setTestInput] = useState('')
  const [testOutput, setTestOutput] = useState('')
  
  // Fetch data
  const { data: scenariosData, isLoading: loadingScenarios } = useQuery({
    queryKey: ['config-scenarios'],
    queryFn: () => configApi.getScenarios(),
  })
  
  const { data: promptsData, isLoading: loadingPrompts } = useQuery({
    queryKey: ['config-prompts'],
    queryFn: () => configApi.getPrompts(),
  })
  
  const { data: kuTypesData, isLoading: loadingKUTypes } = useQuery({
    queryKey: ['config-ku-types'],
    queryFn: () => configApi.getKUTypes(),
  })
  
  // Fetch prompt history when modal is open
  const { data: historyData, isLoading: loadingHistory } = useQuery({
    queryKey: ['prompt-history', historyModal.promptId],
    queryFn: () => historyModal.promptId ? configApi.getPromptHistory(historyModal.promptId) : Promise.resolve({ history: [] }),
    enabled: historyModal.visible && !!historyModal.promptId,
  })
  
  // Mutations
  const updatePromptMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<PromptTemplate> }) => 
      configApi.updatePrompt(id, data),
    onSuccess: () => {
      message.success('Prompt 更新成功')
      queryClient.invalidateQueries({ queryKey: ['config-prompts'] })
      setPromptModal({ visible: false, item: null, isNew: false })
    },
    onError: () => message.error('更新失败'),
  })
  
  const createPromptMutation = useMutation({
    mutationFn: configApi.createPrompt,
    onSuccess: () => {
      message.success('Prompt 创建成功')
      queryClient.invalidateQueries({ queryKey: ['config-prompts'] })
      setPromptModal({ visible: false, item: null, isNew: false })
      promptForm.resetFields()
    },
    onError: () => message.error('创建失败'),
  })
  
  const revertPromptMutation = useMutation({
    mutationFn: ({ promptId, version }: { promptId: number; version: number }) =>
      configApi.revertPrompt(promptId, version),
    onSuccess: () => {
      message.success('已回滚到指定版本')
      queryClient.invalidateQueries({ queryKey: ['config-prompts'] })
      queryClient.invalidateQueries({ queryKey: ['prompt-history'] })
      setHistoryModal({ visible: false, promptId: null, promptName: '' })
    },
    onError: () => message.error('回滚失败'),
  })
  
  const updateScenarioMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Scenario> }) => 
      configApi.updateScenario(id, data),
    onSuccess: () => {
      message.success('场景更新成功')
      queryClient.invalidateQueries({ queryKey: ['config-scenarios'] })
      setScenarioModal({ visible: false, item: null, isNew: false })
    },
    onError: () => message.error('更新失败'),
  })
  
  const createScenarioMutation = useMutation({
    mutationFn: configApi.createScenario,
    onSuccess: () => {
      message.success('场景创建成功')
      queryClient.invalidateQueries({ queryKey: ['config-scenarios'] })
      setScenarioModal({ visible: false, item: null, isNew: false })
      scenarioForm.resetFields()
    },
    onError: () => message.error('创建失败'),
  })
  
  const createKuTypeMutation = useMutation({
    mutationFn: configApi.createKUType,
    onSuccess: () => {
      message.success('KU 类型创建成功')
      queryClient.invalidateQueries({ queryKey: ['config-ku-types'] })
      setKuTypeModal({ visible: false, item: null, isNew: false })
      kuTypeForm.resetFields()
    },
    onError: () => message.error('创建失败'),
  })
  
  const updateKuTypeMutation = useMutation({
    mutationFn: ({ typeCode, data }: { typeCode: string; data: Partial<KUType> }) =>
      configApi.updateKUType(typeCode as unknown as number, data),
    onSuccess: () => {
      message.success('KU 类型更新成功')
      queryClient.invalidateQueries({ queryKey: ['config-ku-types'] })
      setKuTypeModal({ visible: false, item: null, isNew: false })
    },
    onError: () => message.error('更新失败'),
  })
  
  // Form effects
  useEffect(() => {
    if (promptModal.item && !promptModal.isNew) {
      promptForm.setFieldsValue(promptModal.item)
    } else if (promptModal.isNew) {
      promptForm.resetFields()
    }
  }, [promptModal, promptForm])
  
  useEffect(() => {
    if (scenarioModal.item && !scenarioModal.isNew) {
      scenarioForm.setFieldsValue(scenarioModal.item)
    } else if (scenarioModal.isNew) {
      scenarioForm.resetFields()
    }
  }, [scenarioModal, scenarioForm])
  
  useEffect(() => {
    if (kuTypeModal.item && !kuTypeModal.isNew) {
      kuTypeForm.setFieldsValue(kuTypeModal.item)
    } else if (kuTypeModal.isNew) {
      kuTypeForm.resetFields()
    }
  }, [kuTypeModal, kuTypeForm])
  
  const handleSavePrompt = () => {
    promptForm.validateFields().then((values: Record<string, unknown>) => {
      if (promptModal.isNew) {
        createPromptMutation.mutate(values as Parameters<typeof createPromptMutation.mutate>[0])
      } else if (promptModal.item) {
        updatePromptMutation.mutate({ id: promptModal.item.id, data: values })
      }
    })
  }
  
  const handleSaveScenario = () => {
    scenarioForm.validateFields().then((values: Record<string, unknown>) => {
      if (scenarioModal.isNew) {
        createScenarioMutation.mutate(values as Parameters<typeof createScenarioMutation.mutate>[0])
      } else if (scenarioModal.item) {
        updateScenarioMutation.mutate({ id: scenarioModal.item.scenario_id, data: values })
      }
    })
  }
  
  const handleSaveKuType = () => {
    kuTypeForm.validateFields().then((values: Record<string, unknown>) => {
      if (kuTypeModal.isNew) {
        createKuTypeMutation.mutate(values as Parameters<typeof createKuTypeMutation.mutate>[0])
      } else if (kuTypeModal.item) {
        updateKuTypeMutation.mutate({ typeCode: kuTypeModal.item.type_code, data: values })
      }
    })
  }
  
  const handleTestPrompt = () => {
    if (!testModal.prompt) return
    // Simulate test - in production this would call the API
    const template = testModal.prompt.template
    const result = template.replace(/\{\{(\w+)\}\}/g, (_match: string, key: string) => {
      return `[${key}值]`
    })
    setTestOutput(result)
    message.success('模板渲染完成')
  }
  
  // Column definitions
  const scenarioColumns = [
    { title: 'ID', dataIndex: 'scenario_id', key: 'scenario_id' },
    { title: '图标', dataIndex: 'icon', key: 'icon' },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
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
      render: (_: unknown, record: Scenario) => (
        <Space>
          <Button 
            type="link" 
            icon={<EditOutlined />}
            onClick={() => setScenarioModal({ visible: true, item: record, isNew: false })}
          >
            编辑
          </Button>
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
          user: 'cyan',
        }
        return <Tag color={colors[type] || 'default'}>{type}</Tag>
      },
    },
    { 
      title: '场景', 
      dataIndex: 'scenario_id', 
      key: 'scenario_id', 
      render: (id: string | null) => id || '通用' 
    },
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
      render: (_: unknown, record: PromptTemplate) => (
        <Space>
          <Button 
            type="link" 
            icon={<EditOutlined />} 
            onClick={() => setPromptModal({ visible: true, item: record, isNew: false })}
          >
            编辑
          </Button>
          <Button 
            type="link" 
            icon={<HistoryOutlined />}
            onClick={() => setHistoryModal({ visible: true, promptId: record.id, promptName: record.name })}
          >
            历史
          </Button>
          <Button 
            type="link" 
            icon={<PlayCircleOutlined />}
            onClick={() => {
              setTestModal({ visible: true, prompt: record })
              setTestInput('')
              setTestOutput('')
            }}
          >
            测试
          </Button>
        </Space>
      ),
    },
  ]
  
  const kuTypeColumns = [
    { title: '类型代码', dataIndex: 'type_code', key: 'type_code' },
    { 
      title: '分类', 
      dataIndex: 'category', 
      key: 'category',
      render: (cat: string) => {
        const colors: Record<string, string> = {
          product: 'blue',
          solution: 'purple',
          case: 'green',
          quote: 'orange',
          biz: 'cyan',
          delivery: 'geekblue',
          field: 'magenta',
          sales: 'gold',
        }
        return <Tag color={colors[cat] || 'default'}>{cat}</Tag>
      }
    },
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
        return <Tag color={colors[strategy] || 'default'}>{strategy}</Tag>
      },
    },
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
      render: (_: unknown, record: KUType) => (
        <Button 
          type="link" 
          icon={<EditOutlined />}
          onClick={() => setKuTypeModal({ visible: true, item: record, isNew: false })}
        >
          编辑
        </Button>
      ),
    },
  ]
  
  const tabItems = [
    {
      key: 'scenarios',
      label: '场景配置',
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setScenarioModal({ visible: true, item: null, isNew: true })}
            >
              新建场景
            </Button>
          </div>
          <Spin spinning={loadingScenarios}>
            <Table 
              dataSource={scenariosData?.scenarios ?? []} 
              columns={scenarioColumns} 
              rowKey="scenario_id" 
              locale={{ emptyText: '暂无场景配置' }}
            />
          </Spin>
        </div>
      ),
    },
    {
      key: 'prompts',
      label: 'Prompt 模板',
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setPromptModal({ visible: true, item: null, isNew: true })}
            >
              新建 Prompt
            </Button>
          </div>
          <Spin spinning={loadingPrompts}>
            <Table 
              dataSource={promptsData?.prompts ?? []} 
              columns={promptColumns} 
              rowKey="id" 
              locale={{ emptyText: '暂无 Prompt 模板' }}
            />
          </Spin>
        </div>
      ),
    },
    {
      key: 'ku-types',
      label: 'KU 类型',
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setKuTypeModal({ visible: true, item: null, isNew: true })}
            >
              新建类型
            </Button>
          </div>
          <Spin spinning={loadingKUTypes}>
            <Table 
              dataSource={kuTypesData?.ku_types ?? []} 
              columns={kuTypeColumns} 
              rowKey="type_code" 
              locale={{ emptyText: '暂无 KU 类型' }}
            />
          </Spin>
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
        title={promptModal.isNew ? '新建 Prompt' : `编辑: ${promptModal.item?.name || ''}`}
        open={promptModal.visible}
        onCancel={() => setPromptModal({ visible: false, item: null, isNew: false })}
        onOk={handleSavePrompt}
        confirmLoading={updatePromptMutation.isPending || createPromptMutation.isPending}
        width={800}
      >
        <Form form={promptForm} layout="vertical">
          <Form.Item 
            label="名称" 
            name="name" 
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="Prompt 名称" />
          </Form.Item>
          
          <Form.Item 
            label="类型" 
            name="type" 
            rules={[{ required: true, message: '请选择类型' }]}
          >
            <Select placeholder="选择类型">
              <Select.Option value="system">System</Select.Option>
              <Select.Option value="response">Response</Select.Option>
              <Select.Option value="intent">Intent</Select.Option>
              <Select.Option value="summary">Summary</Select.Option>
              <Select.Option value="user">User</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="场景" name="scenario_id">
            <Select allowClear placeholder="通用">
              {(scenariosData?.scenarios ?? []).map((s: Scenario) => (
                <Select.Option key={s.scenario_id} value={s.scenario_id}>{s.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item 
            label="模板内容" 
            name="template" 
            rules={[{ required: true, message: '请输入模板内容' }]}
            extra="使用 {{variable}} 定义变量，如 {{user_name}}, {{context}}, {{query}}"
          >
            <TextArea rows={10} placeholder="输入 Prompt 模板..." />
          </Form.Item>
          
          {!promptModal.isNew && (
            <Form.Item label="变更原因" name="change_reason">
              <Input placeholder="描述本次修改的原因" />
            </Form.Item>
          )}
        </Form>
      </Modal>
      
      {/* Scenario Edit Modal */}
      <Modal
        title={scenarioModal.isNew ? '新建场景' : `编辑: ${scenarioModal.item?.name || ''}`}
        open={scenarioModal.visible}
        onCancel={() => setScenarioModal({ visible: false, item: null, isNew: false })}
        onOk={handleSaveScenario}
        confirmLoading={updateScenarioMutation.isPending || createScenarioMutation.isPending}
        width={600}
      >
        <Form form={scenarioForm} layout="vertical">
          <Form.Item 
            label="场景 ID" 
            name="scenario_id" 
            rules={[{ required: true }]}
          >
            <Input disabled={!scenarioModal.isNew} placeholder="param_query" />
          </Form.Item>
          
          <Form.Item 
            label="名称" 
            name="name" 
            rules={[{ required: true }]}
          >
            <Input placeholder="场景名称" />
          </Form.Item>
          
          <Form.Item label="描述" name="description">
            <TextArea rows={2} placeholder="场景描述" />
          </Form.Item>
          
          <Form.Item label="图标" name="icon">
            <Input placeholder="图标 emoji，如 📊" />
          </Form.Item>
          
          <Form.Item label="状态" name="is_active" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
      
      {/* KU Type Edit Modal */}
      <Modal
        title={kuTypeModal.isNew ? '新建 KU 类型' : `编辑: ${kuTypeModal.item?.display_name || ''}`}
        open={kuTypeModal.visible}
        onCancel={() => setKuTypeModal({ visible: false, item: null, isNew: false })}
        onOk={handleSaveKuType}
        confirmLoading={createKuTypeMutation.isPending || updateKuTypeMutation.isPending}
        width={600}
      >
        <Form form={kuTypeForm} layout="vertical">
          <Form.Item 
            label="类型代码" 
            name="type_code" 
            rules={[{ required: true }]}
            extra="格式: category.name，如 core.product_feature"
          >
            <Input disabled={!kuTypeModal.isNew} placeholder="core.product_feature" />
          </Form.Item>
          
          <Form.Item 
            label="分类" 
            name="category" 
            rules={[{ required: true }]}
          >
            <Select placeholder="选择分类" disabled={!kuTypeModal.isNew}>
              <Select.Option value="product">产品与技术</Select.Option>
              <Select.Option value="solution">解决方案</Select.Option>
              <Select.Option value="case">案例</Select.Option>
              <Select.Option value="quote">报价</Select.Option>
              <Select.Option value="biz">商务</Select.Option>
              <Select.Option value="delivery">交付</Select.Option>
              <Select.Option value="field">现场</Select.Option>
              <Select.Option value="sales">销售</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item 
            label="显示名称" 
            name="display_name" 
            rules={[{ required: true }]}
          >
            <Input placeholder="产品功能说明" />
          </Form.Item>
          
          <Form.Item label="描述" name="description">
            <TextArea rows={2} placeholder="类型描述" />
          </Form.Item>
          
          <Form.Item label="合并策略" name="merge_strategy" initialValue="independent">
            <Select>
              <Select.Option value="smart_merge">智能合并</Select.Option>
              <Select.Option value="independent">独立存储</Select.Option>
              <Select.Option value="append">追加</Select.Option>
            </Select>
          </Form.Item>
          
          <Space style={{ width: '100%' }}>
            <Form.Item label="需要过期日期" name="requires_expiry" valuePropName="checked">
              <Switch />
            </Form.Item>
            
            <Form.Item label="需要审批" name="requires_approval" valuePropName="checked">
              <Switch defaultChecked />
            </Form.Item>
            
            <Form.Item label="启用" name="is_active" valuePropName="checked">
              <Switch defaultChecked />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
      
      {/* Prompt History Modal */}
      <Modal
        title={`Prompt 历史: ${historyModal.promptName}`}
        open={historyModal.visible}
        onCancel={() => setHistoryModal({ visible: false, promptId: null, promptName: '' })}
        footer={null}
        width={800}
      >
        <Spin spinning={loadingHistory}>
          <List
            dataSource={historyData?.history ?? []}
            locale={{ emptyText: '暂无历史版本' }}
            renderItem={(item: PromptHistoryItem) => (
              <List.Item
                actions={[
                  <Button
                    key="revert"
                    type="link"
                    icon={<RollbackOutlined />}
                    onClick={() => {
                      Modal.confirm({
                        title: '确认回滚?',
                        content: `将回滚到版本 v${item.version}`,
                        onOk: () => {
                          if (historyModal.promptId) {
                            revertPromptMutation.mutate({ promptId: historyModal.promptId, version: item.version })
                          }
                        },
                      })
                    }}
                  >
                    回滚到此版本
                  </Button>
                ]}
              >
                <List.Item.Meta
                  title={<Text strong>v{item.version}</Text>}
                  description={
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {item.created_at} {item.change_reason && `- ${item.change_reason}`}
                      </Text>
                      <Paragraph 
                        ellipsis={{ rows: 3, expandable: true }}
                        style={{ marginTop: 8, marginBottom: 0, background: '#1e293b', padding: 12, borderRadius: 4 }}
                      >
                        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
                          {item.template}
                        </pre>
                      </Paragraph>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Spin>
      </Modal>
      
      {/* Prompt Test Modal */}
      <Modal
        title={`测试 Prompt: ${testModal.prompt?.name || ''}`}
        open={testModal.visible}
        onCancel={() => setTestModal({ visible: false, prompt: null })}
        footer={[
          <Button key="cancel" onClick={() => setTestModal({ visible: false, prompt: null })}>
            关闭
          </Button>,
          <Button key="test" type="primary" onClick={handleTestPrompt}>
            渲染测试
          </Button>,
        ]}
        width={800}
      >
        <div style={{ marginBottom: 16 }}>
          <Text strong>模板内容:</Text>
          <div style={{ background: '#1e293b', padding: 12, borderRadius: 4, marginTop: 8, maxHeight: 200, overflow: 'auto' }}>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
              {testModal.prompt?.template}
            </pre>
          </div>
        </div>
        
        <div style={{ marginBottom: 16 }}>
          <Text strong>测试输入 (JSON格式的变量值):</Text>
          <TextArea
            rows={4}
            value={testInput}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setTestInput(e.target.value)}
            placeholder='{"user_name": "张三", "context": "检索到的内容...", "query": "用户问题"}'
            style={{ marginTop: 8 }}
          />
        </div>
        
        {testOutput && (
          <div>
            <Text strong>渲染结果:</Text>
            <div style={{ background: '#1e293b', padding: 12, borderRadius: 4, marginTop: 8 }}>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
                {testOutput}
              </pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
