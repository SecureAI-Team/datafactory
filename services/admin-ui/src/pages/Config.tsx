import React, { useState, useEffect } from 'react'
import { Card, Tabs, Table, Button, Space, Tag, Modal, Form, Input, Select, message, Typography, Spin, List, Switch, InputNumber } from 'antd'
import { PlusOutlined, EditOutlined, HistoryOutlined, PlayCircleOutlined, RollbackOutlined, DeleteOutlined, CodeOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, Scenario, PromptTemplate, KUType, ParameterDefinition, CalculationRule, CreateParameterRequest, CreateCalcRuleRequest } from '../api'

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
  
  // Parameter and CalcRule modals
  const [paramModal, setParamModal] = useState<{ visible: boolean; item: ParameterDefinition | null; isNew: boolean }>({
    visible: false,
    item: null,
    isNew: false,
  })
  const [calcRuleModal, setCalcRuleModal] = useState<{ visible: boolean; item: CalculationRule | null; isNew: boolean }>({
    visible: false,
    item: null,
    isNew: false,
  })
  const [calcTestModal, setCalcTestModal] = useState<{ visible: boolean; rule: CalculationRule | null }>({
    visible: false,
    rule: null,
  })
  const [calcTestInputs, setCalcTestInputs] = useState<Record<string, string>>({})
  const [calcTestResult, setCalcTestResult] = useState<string>('')
  
  const [paramForm] = Form.useForm()
  const [calcRuleForm] = Form.useForm()
  
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
  
  // Fetch parameters
  const { data: parametersData, isLoading: loadingParameters } = useQuery({
    queryKey: ['config-parameters'],
    queryFn: () => configApi.getParameters(),
  })
  
  // Fetch calculation rules
  const { data: calcRulesData, isLoading: loadingCalcRules } = useQuery({
    queryKey: ['config-calc-rules'],
    queryFn: () => configApi.getCalcRules(),
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
      configApi.updateKUType(typeCode, data),
    onSuccess: () => {
      message.success('KU 类型更新成功')
      queryClient.invalidateQueries({ queryKey: ['config-ku-types'] })
      setKuTypeModal({ visible: false, item: null, isNew: false })
    },
    onError: () => message.error('更新失败'),
  })
  
  // Parameter mutations
  const createParamMutation = useMutation({
    mutationFn: (data: CreateParameterRequest) => configApi.createParameter(data),
    onSuccess: () => {
      message.success('参数创建成功')
      queryClient.invalidateQueries({ queryKey: ['config-parameters'] })
      setParamModal({ visible: false, item: null, isNew: false })
      paramForm.resetFields()
    },
    onError: () => message.error('创建失败'),
  })
  
  const updateParamMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<CreateParameterRequest> }) =>
      configApi.updateParameter(id, data),
    onSuccess: () => {
      message.success('参数更新成功')
      queryClient.invalidateQueries({ queryKey: ['config-parameters'] })
      setParamModal({ visible: false, item: null, isNew: false })
    },
    onError: () => message.error('更新失败'),
  })
  
  const deleteParamMutation = useMutation({
    mutationFn: (id: number) => configApi.deleteParameter(id),
    onSuccess: () => {
      message.success('参数已删除')
      queryClient.invalidateQueries({ queryKey: ['config-parameters'] })
    },
    onError: () => message.error('删除失败'),
  })
  
  // Calc rule mutations
  const createCalcRuleMutation = useMutation({
    mutationFn: (data: CreateCalcRuleRequest) => configApi.createCalcRule(data),
    onSuccess: () => {
      message.success('计算规则创建成功')
      queryClient.invalidateQueries({ queryKey: ['config-calc-rules'] })
      setCalcRuleModal({ visible: false, item: null, isNew: false })
      calcRuleForm.resetFields()
    },
    onError: () => message.error('创建失败'),
  })
  
  const updateCalcRuleMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<CreateCalcRuleRequest> }) =>
      configApi.updateCalcRule(id, data),
    onSuccess: () => {
      message.success('计算规则更新成功')
      queryClient.invalidateQueries({ queryKey: ['config-calc-rules'] })
      setCalcRuleModal({ visible: false, item: null, isNew: false })
    },
    onError: () => message.error('更新失败'),
  })
  
  const testCalcRuleMutation = useMutation({
    mutationFn: ({ ruleId, inputs }: { ruleId: number; inputs: Record<string, unknown> }) =>
      configApi.testCalcRule(ruleId, inputs),
    onSuccess: (data) => {
      setCalcTestResult(data.success ? JSON.stringify(data.result, null, 2) : `错误: ${data.error}`)
      if (data.success) {
        message.success('测试完成')
      } else {
        message.error(`测试失败: ${data.error}`)
      }
    },
    onError: () => message.error('测试失败'),
  })
  
  // Form effects
  useEffect(() => {
    if (promptModal.item && !promptModal.isNew) {
      // Exclude 'variables' field as it's not editable in the form
      // and contains objects that can cause React render errors
      const { variables: _variables, ...formValues } = promptModal.item
      promptForm.setFieldsValue(formValues)
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
  
  useEffect(() => {
    if (paramModal.item && !paramModal.isNew) {
      paramForm.setFieldsValue({
        ...paramModal.item,
        synonyms: paramModal.item.synonyms?.join(', ') || '',
      })
    } else if (paramModal.isNew) {
      paramForm.resetFields()
    }
  }, [paramModal, paramForm])
  
  useEffect(() => {
    if (calcRuleModal.item && !calcRuleModal.isNew) {
      // Exclude complex object fields to prevent React render errors
      const { 
        examples: _examples, 
        input_schema: _inputSchema, 
        output_schema: _outputSchema,
        ...safeFields 
      } = calcRuleModal.item as unknown as Record<string, unknown>
      calcRuleForm.setFieldsValue({
        ...safeFields,
        input_params: calcRuleModal.item.input_params?.join(', ') || '',
      })
    } else if (calcRuleModal.isNew) {
      calcRuleForm.resetFields()
    }
  }, [calcRuleModal, calcRuleForm])
  
  const handleSavePrompt = () => {
    promptForm.validateFields().then((values) => {
      if (promptModal.isNew) {
        createPromptMutation.mutate({
          name: values.name as string,
          type: values.type as string,
          template: values.template as string,
          scenario_id: values.scenario_id as string | undefined,
        })
      } else if (promptModal.item) {
        updatePromptMutation.mutate({ id: promptModal.item.id, data: values })
      }
    })
  }
  
  const handleSaveScenario = () => {
    scenarioForm.validateFields().then((values) => {
      if (scenarioModal.isNew) {
        createScenarioMutation.mutate({
          scenario_id: values.scenario_id as string,
          name: values.name as string,
          description: values.description as string | undefined,
          icon: values.icon as string | undefined,
          is_active: values.is_active as boolean | undefined,
        })
      } else if (scenarioModal.item) {
        updateScenarioMutation.mutate({ id: scenarioModal.item.scenario_id, data: values })
      }
    })
  }
  
  const handleSaveKuType = () => {
    kuTypeForm.validateFields().then((values) => {
      if (kuTypeModal.isNew) {
        createKuTypeMutation.mutate({
          type_code: values.type_code as string,
          category: values.category as string,
          display_name: values.display_name as string,
          description: values.description as string | undefined,
          merge_strategy: values.merge_strategy as string | undefined,
          requires_expiry: values.requires_expiry as boolean | undefined,
          requires_approval: values.requires_approval as boolean | undefined,
          is_active: values.is_active as boolean | undefined,
        })
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
  
  const handleSaveParam = () => {
    paramForm.validateFields().then((values: Record<string, unknown>) => {
      const data = {
        ...values,
        synonyms: typeof values.synonyms === 'string' 
          ? (values.synonyms as string).split(',').map((s: string) => s.trim()).filter(Boolean)
          : [],
      }
      if (paramModal.isNew) {
        createParamMutation.mutate(data as unknown as CreateParameterRequest)
      } else if (paramModal.item) {
        updateParamMutation.mutate({ id: paramModal.item.id, data: data as Partial<CreateParameterRequest> })
      }
    })
  }
  
  const handleSaveCalcRule = () => {
    calcRuleForm.validateFields().then((values: Record<string, unknown>) => {
      const data = {
        ...values,
        input_params: typeof values.input_params === 'string'
          ? (values.input_params as string).split(',').map((s: string) => s.trim()).filter(Boolean)
          : [],
      }
      if (calcRuleModal.isNew) {
        createCalcRuleMutation.mutate(data as unknown as CreateCalcRuleRequest)
      } else if (calcRuleModal.item) {
        updateCalcRuleMutation.mutate({ id: calcRuleModal.item.id, data: data as Partial<CreateCalcRuleRequest> })
      }
    })
  }
  
  const handleTestCalcRule = () => {
    if (!calcTestModal.rule) return
    const inputs: Record<string, unknown> = {}
    calcTestModal.rule.input_params.forEach(param => {
      const val = calcTestInputs[param]
      inputs[param] = isNaN(Number(val)) ? val : Number(val)
    })
    testCalcRuleMutation.mutate({ ruleId: calcTestModal.rule.id, inputs })
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
  
  // Parameter columns
  const paramColumns = [
    { title: '参数名称', dataIndex: 'name', key: 'name' },
    { title: '代码', dataIndex: 'code', key: 'code' },
    { 
      title: '数据类型', 
      dataIndex: 'data_type', 
      key: 'data_type',
      render: (type: string) => <Tag>{type}</Tag>
    },
    { title: '单位', dataIndex: 'unit', key: 'unit', render: (u: string) => u || '-' },
    { title: '分类', dataIndex: 'category', key: 'category', render: (c: string) => c || '-' },
    {
      title: '同义词',
      dataIndex: 'synonyms',
      key: 'synonyms',
      render: (syns: string[]) => syns?.length > 0 ? syns.slice(0, 2).join(', ') + (syns.length > 2 ? '...' : '') : '-'
    },
    {
      title: '系统内置',
      dataIndex: 'is_system',
      key: 'is_system',
      render: (sys: boolean) => sys ? <Tag color="purple">系统</Tag> : <Tag>自定义</Tag>
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: ParameterDefinition) => (
        <Space>
          <Button 
            type="link" 
            icon={<EditOutlined />}
            onClick={() => setParamModal({ visible: true, item: record, isNew: false })}
          >
            编辑
          </Button>
          {!record.is_system && (
            <Button 
              type="link" 
              danger
              icon={<DeleteOutlined />}
              onClick={() => {
                Modal.confirm({
                  title: '确认删除?',
                  content: `确定要删除参数 "${record.name}" 吗?`,
                  onOk: () => deleteParamMutation.mutate(record.id),
                })
              }}
            >
              删除
            </Button>
          )}
        </Space>
      ),
    },
  ]
  
  // Calc rule columns
  const calcRuleColumns = [
    { title: '规则名称', dataIndex: 'name', key: 'name' },
    { title: '代码', dataIndex: 'code', key: 'code' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true, render: (d: string) => d || '-' },
    { 
      title: '输入参数', 
      dataIndex: 'input_params', 
      key: 'input_params',
      render: (params: string[]) => params?.map((p: string) => <Tag key={p}>{p}</Tag>)
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => <Tag color={active ? 'green' : 'default'}>{active ? '启用' : '禁用'}</Tag>
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: CalculationRule) => (
        <Space>
          <Button 
            type="link" 
            icon={<EditOutlined />}
            onClick={() => setCalcRuleModal({ visible: true, item: record, isNew: false })}
          >
            编辑
          </Button>
          <Button 
            type="link" 
            icon={<CodeOutlined />}
            onClick={() => {
              setCalcTestModal({ visible: true, rule: record })
              setCalcTestInputs({})
              setCalcTestResult('')
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
    {
      key: 'parameters',
      label: '参数定义',
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setParamModal({ visible: true, item: null, isNew: true })}
            >
              新建参数
            </Button>
          </div>
          <Spin spinning={loadingParameters}>
            <Table 
              dataSource={parametersData?.parameters ?? []} 
              columns={paramColumns} 
              rowKey="id" 
              locale={{ emptyText: '暂无参数定义' }}
            />
          </Spin>
        </div>
      ),
    },
    {
      key: 'calc-rules',
      label: '计算规则',
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setCalcRuleModal({ visible: true, item: null, isNew: true })}
            >
              新建规则
            </Button>
          </div>
          <Spin spinning={loadingCalcRules}>
            <Table 
              dataSource={calcRulesData?.rules ?? []} 
              columns={calcRuleColumns} 
              rowKey="id" 
              locale={{ emptyText: '暂无计算规则' }}
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
      
      {/* Parameter Edit Modal */}
      <Modal
        title={paramModal.isNew ? '新建参数' : `编辑: ${paramModal.item?.name || ''}`}
        open={paramModal.visible}
        onCancel={() => setParamModal({ visible: false, item: null, isNew: false })}
        onOk={handleSaveParam}
        confirmLoading={createParamMutation.isPending || updateParamMutation.isPending}
        width={600}
      >
        <Form form={paramForm} layout="vertical">
          <Form.Item 
            label="参数名称" 
            name="name" 
            rules={[{ required: true, message: '请输入参数名称' }]}
          >
            <Input placeholder="检测精度" />
          </Form.Item>
          
          <Form.Item 
            label="代码" 
            name="code" 
            rules={[{ required: true, message: '请输入参数代码' }]}
          >
            <Input placeholder="detection_accuracy" disabled={!paramModal.isNew} />
          </Form.Item>
          
          <Form.Item 
            label="数据类型" 
            name="data_type" 
            rules={[{ required: true }]}
          >
            <Select placeholder="选择数据类型">
              <Select.Option value="string">字符串</Select.Option>
              <Select.Option value="number">数字</Select.Option>
              <Select.Option value="boolean">布尔值</Select.Option>
              <Select.Option value="array">数组</Select.Option>
              <Select.Option value="object">对象</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="单位" name="unit">
            <Input placeholder="mm" />
          </Form.Item>
          
          <Form.Item label="分类" name="category">
            <Input placeholder="AOI" />
          </Form.Item>
          
          <Form.Item 
            label="同义词" 
            name="synonyms"
            extra="多个同义词用逗号分隔"
          >
            <Input placeholder="精度, 检测分辨率" />
          </Form.Item>
        </Form>
      </Modal>
      
      {/* Calc Rule Edit Modal */}
      <Modal
        title={calcRuleModal.isNew ? '新建计算规则' : `编辑: ${calcRuleModal.item?.name || ''}`}
        open={calcRuleModal.visible}
        onCancel={() => setCalcRuleModal({ visible: false, item: null, isNew: false })}
        onOk={handleSaveCalcRule}
        confirmLoading={createCalcRuleMutation.isPending || updateCalcRuleMutation.isPending}
        width={700}
      >
        <Form form={calcRuleForm} layout="vertical">
          <Form.Item 
            label="规则名称" 
            name="name" 
            rules={[{ required: true, message: '请输入规则名称' }]}
          >
            <Input placeholder="产能计算" />
          </Form.Item>
          
          <Form.Item 
            label="代码" 
            name="code" 
            rules={[{ required: true, message: '请输入规则代码' }]}
          >
            <Input placeholder="capacity_calc" disabled={!calcRuleModal.isNew} />
          </Form.Item>
          
          <Form.Item label="描述" name="description">
            <TextArea rows={2} placeholder="规则描述" />
          </Form.Item>
          
          <Form.Item 
            label="公式" 
            name="formula" 
            rules={[{ required: true, message: '请输入计算公式' }]}
            extra="使用变量名编写公式，如: scan_speed * 3600 * work_hours"
          >
            <TextArea rows={3} placeholder="scan_speed * 3600 * work_hours" />
          </Form.Item>
          
          <Form.Item 
            label="输入参数" 
            name="input_params"
            rules={[{ required: true }]}
            extra="多个参数用逗号分隔"
          >
            <Input placeholder="scan_speed, work_hours" />
          </Form.Item>
          
          <Form.Item label="输出类型" name="output_type" initialValue="number">
            <Select>
              <Select.Option value="number">数字</Select.Option>
              <Select.Option value="string">字符串</Select.Option>
              <Select.Option value="boolean">布尔值</Select.Option>
              <Select.Option value="object">对象</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="状态" name="is_active" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
      
      {/* Calc Rule Test Modal */}
      <Modal
        title={`测试规则: ${calcTestModal.rule?.name || ''}`}
        open={calcTestModal.visible}
        onCancel={() => setCalcTestModal({ visible: false, rule: null })}
        footer={[
          <Button key="cancel" onClick={() => setCalcTestModal({ visible: false, rule: null })}>
            关闭
          </Button>,
          <Button 
            key="test" 
            type="primary" 
            onClick={handleTestCalcRule}
            loading={testCalcRuleMutation.isPending}
          >
            执行测试
          </Button>,
        ]}
        width={600}
      >
        {calcTestModal.rule && (
          <>
            <div style={{ marginBottom: 16 }}>
              <Text strong>公式:</Text>
              <div style={{ background: '#1e293b', padding: 12, borderRadius: 4, marginTop: 8 }}>
                <code>{calcTestModal.rule.formula}</code>
              </div>
            </div>
            
            <div style={{ marginBottom: 16 }}>
              <Text strong>输入参数:</Text>
              <div style={{ marginTop: 8 }}>
                {calcTestModal.rule.input_params.map(param => (
                  <div key={param} style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Tag>{param}</Tag>
                    <InputNumber
                      style={{ flex: 1 }}
                      placeholder={`输入 ${param} 的值`}
                      value={calcTestInputs[param] ? Number(calcTestInputs[param]) : undefined}
                      onChange={(value) => setCalcTestInputs(prev => ({ ...prev, [param]: String(value || '') }))}
                    />
                  </div>
                ))}
              </div>
            </div>
            
            {calcTestResult && (
              <div>
                <Text strong>计算结果:</Text>
                <div style={{ background: '#1e293b', padding: 12, borderRadius: 4, marginTop: 8 }}>
                  <pre style={{ margin: 0, color: '#22c55e' }}>{calcTestResult}</pre>
                </div>
              </div>
            )}
          </>
        )}
      </Modal>
    </div>
  )
}
