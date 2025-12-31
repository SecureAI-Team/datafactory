import { useState, useEffect } from 'react'
import { Card, Table, Tag, Button, Space, Modal, Form, Input, Select, message, Typography, Avatar } from 'antd'
import { PlusOutlined, EditOutlined, StopOutlined, UserOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi, User } from '../api'

const { Title } = Typography

const roleColors: Record<string, string> = {
  admin: 'red',
  data_ops: 'purple',
  bd_sales: 'blue',
  user: 'default',
}

const roleNames: Record<string, string> = {
  admin: '管理员',
  data_ops: '数据运维',
  bd_sales: 'BD/销售',
  user: '普通用户',
}

export default function Users() {
  const queryClient = useQueryClient()
  const [createModal, setCreateModal] = useState(false)
  const [editModal, setEditModal] = useState<{ visible: boolean; user: User | null }>({
    visible: false,
    user: null,
  })
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  
  // Fetch users
  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersApi.list({ limit: 100 }),
  })
  
  // Create user mutation
  const createMutation = useMutation({
    mutationFn: usersApi.create,
    onSuccess: () => {
      message.success('用户创建成功')
      setCreateModal(false)
      createForm.resetFields()
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (error: Error) => {
      message.error(`创建失败: ${error.message}`)
    },
  })
  
  // Update user mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof usersApi.update>[1] }) => 
      usersApi.update(id, data),
    onSuccess: () => {
      message.success('用户更新成功')
      setEditModal({ visible: false, user: null })
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (error: Error) => {
      message.error(`更新失败: ${error.message}`)
    },
  })
  
  // Delete/disable user mutation
  const deleteMutation = useMutation({
    mutationFn: usersApi.delete,
    onSuccess: () => {
      message.success('用户已禁用')
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (error: Error) => {
      message.error(`操作失败: ${error.message}`)
    },
  })
  
  // Set edit form values when user changes
  useEffect(() => {
    if (editModal.user) {
      editForm.setFieldsValue(editModal.user)
    }
  }, [editModal.user, editForm])
  
  const handleCreate = () => {
    createForm.validateFields().then((values) => {
      createMutation.mutate(values)
    })
  }
  
  const handleUpdate = () => {
    editForm.validateFields().then((values) => {
      if (editModal.user) {
        updateMutation.mutate({ id: editModal.user.id, data: values })
      }
    })
  }
  
  const handleDisable = (user: User) => {
    Modal.confirm({
      title: '确认禁用',
      content: `确定要禁用用户 "${user.display_name || user.username}" 吗？`,
      onOk: () => {
        deleteMutation.mutate(user.id)
      },
    })
  }
  
  const handleEnable = (user: User) => {
    updateMutation.mutate({ id: user.id, data: { is_active: true } })
  }
  
  const columns = [
    {
      title: '用户',
      key: 'user',
      render: (_: unknown, record: User) => (
        <Space>
          <Avatar style={{ backgroundColor: record.is_active ? '#0ea5e9' : '#64748b' }}>
            {record.display_name?.[0] || record.username[0].toUpperCase()}
          </Avatar>
          <div>
            <div>{record.display_name || record.username}</div>
            <div style={{ fontSize: 12, color: '#64748b' }}>{record.email}</div>
          </div>
        </Space>
      ),
    },
    { title: '用户名', dataIndex: 'username', key: 'username' },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => (
        <Tag color={roleColors[role] || 'default'}>{roleNames[role] || role}</Tag>
      ),
    },
    { title: '部门', dataIndex: 'department', key: 'department', render: (d: string) => d || '-' },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'default'}>{active ? '正常' : '已禁用'}</Tag>
      ),
    },
    { 
      title: '最后登录', 
      dataIndex: 'last_login_at', 
      key: 'last_login_at',
      render: (t: string) => t || '从未登录'
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: User) => (
        <Space>
          <Button 
            type="link" 
            icon={<EditOutlined />} 
            onClick={() => setEditModal({ visible: true, user: record })}
          >
            编辑
          </Button>
          {record.is_active && record.role !== 'admin' && (
            <Button 
              type="link" 
              danger 
              icon={<StopOutlined />} 
              onClick={() => handleDisable(record)}
              loading={deleteMutation.isPending}
            >
              禁用
            </Button>
          )}
          {!record.is_active && (
            <Button 
              type="link" 
              icon={<CheckCircleOutlined />} 
              onClick={() => handleEnable(record)}
              loading={updateMutation.isPending}
            >
              启用
            </Button>
          )}
        </Space>
      ),
    },
  ]
  
  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>用户管理</Title>
      
      <Card>
        <div style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModal(true)}>
            新建用户
          </Button>
        </div>
        
        <Table 
          dataSource={data?.users ?? []} 
          columns={columns} 
          rowKey="id" 
          loading={isLoading}
          locale={{ emptyText: '暂无用户' }}
        />
      </Card>
      
      {/* Create User Modal */}
      <Modal
        title="新建用户"
        open={createModal}
        onCancel={() => {
          setCreateModal(false)
          createForm.resetFields()
        }}
        onOk={handleCreate}
        confirmLoading={createMutation.isPending}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item 
            label="用户名" 
            name="username" 
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          
          <Form.Item 
            label="邮箱" 
            name="email" 
            rules={[{ required: true, type: 'email', message: '请输入有效邮箱' }]}
          >
            <Input placeholder="email@example.com" />
          </Form.Item>
          
          <Form.Item 
            label="密码" 
            name="password" 
            rules={[{ required: true, min: 8, message: '密码至少8位' }]}
          >
            <Input.Password placeholder="密码" />
          </Form.Item>
          
          <Form.Item label="显示名称" name="display_name">
            <Input placeholder="显示名称" />
          </Form.Item>
          
          <Form.Item label="角色" name="role" rules={[{ required: true, message: '请选择角色' }]}>
            <Select placeholder="选择角色">
              <Select.Option value="admin">管理员</Select.Option>
              <Select.Option value="data_ops">数据运维</Select.Option>
              <Select.Option value="bd_sales">BD/销售</Select.Option>
              <Select.Option value="user">普通用户</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="部门" name="department">
            <Input placeholder="部门" />
          </Form.Item>
        </Form>
      </Modal>
      
      {/* Edit User Modal */}
      <Modal
        title={`编辑用户: ${editModal.user?.display_name || editModal.user?.username || ''}`}
        open={editModal.visible}
        onCancel={() => setEditModal({ visible: false, user: null })}
        onOk={handleUpdate}
        confirmLoading={updateMutation.isPending}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item label="显示名称" name="display_name">
            <Input placeholder="显示名称" />
          </Form.Item>
          
          <Form.Item 
            label="邮箱" 
            name="email" 
            rules={[{ type: 'email', message: '请输入有效邮箱' }]}
          >
            <Input placeholder="email@example.com" />
          </Form.Item>
          
          <Form.Item label="角色" name="role" rules={[{ required: true, message: '请选择角色' }]}>
            <Select placeholder="选择角色">
              <Select.Option value="admin">管理员</Select.Option>
              <Select.Option value="data_ops">数据运维</Select.Option>
              <Select.Option value="bd_sales">BD/销售</Select.Option>
              <Select.Option value="user">普通用户</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item label="部门" name="department">
            <Input placeholder="部门" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
