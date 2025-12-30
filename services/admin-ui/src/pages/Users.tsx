import { useState } from 'react'
import { Card, Table, Tag, Button, Space, Modal, Form, Input, Select, message, Typography, Avatar } from 'antd'
import { PlusOutlined, EditOutlined, StopOutlined, UserOutlined } from '@ant-design/icons'

const { Title } = Typography

// Mock data
const mockUsers = [
  { id: 1, username: 'admin', email: 'admin@example.com', display_name: '系统管理员', role: 'admin', department: 'IT', is_active: true, last_login_at: '2024-01-20 10:30' },
  { id: 2, username: 'zhangsan', email: 'zhangsan@example.com', display_name: '张三', role: 'bd_sales', department: '销售部', is_active: true, last_login_at: '2024-01-20 14:15' },
  { id: 3, username: 'lisi', email: 'lisi@example.com', display_name: '李四', role: 'data_ops', department: '数据运维', is_active: true, last_login_at: '2024-01-19 16:45' },
  { id: 4, username: 'wangwu', email: 'wangwu@example.com', display_name: '王五', role: 'bd_sales', department: '销售部', is_active: false, last_login_at: '2024-01-10 09:00' },
]

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
  const [createModal, setCreateModal] = useState(false)
  const [editModal, setEditModal] = useState<{ visible: boolean; user: typeof mockUsers[0] | null }>({
    visible: false,
    user: null,
  })
  const [form] = Form.useForm()
  
  const handleCreate = () => {
    form.validateFields().then(() => {
      message.success('用户创建成功')
      setCreateModal(false)
      form.resetFields()
    })
  }
  
  const handleUpdate = () => {
    form.validateFields().then(() => {
      message.success('用户更新成功')
      setEditModal({ visible: false, user: null })
    })
  }
  
  const handleDisable = (id: number) => {
    Modal.confirm({
      title: '确认禁用',
      content: '确定要禁用该用户吗？',
      onOk: () => {
        message.success(`用户 #${id} 已禁用`)
      },
    })
  }
  
  const columns = [
    {
      title: '用户',
      key: 'user',
      render: (_: unknown, record: typeof mockUsers[0]) => (
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
        <Tag color={roleColors[role]}>{roleNames[role]}</Tag>
      ),
    },
    { title: '部门', dataIndex: 'department', key: 'department' },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'default'}>{active ? '正常' : '已禁用'}</Tag>
      ),
    },
    { title: '最后登录', dataIndex: 'last_login_at', key: 'last_login_at' },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: typeof mockUsers[0]) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => setEditModal({ visible: true, user: record })}>
            编辑
          </Button>
          {record.is_active && record.role !== 'admin' && (
            <Button type="link" danger icon={<StopOutlined />} onClick={() => handleDisable(record.id)}>
              禁用
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
        
        <Table dataSource={mockUsers} columns={columns} rowKey="id" />
      </Card>
      
      {/* Create User Modal */}
      <Modal
        title="新建用户"
        open={createModal}
        onCancel={() => {
          setCreateModal(false)
          form.resetFields()
        }}
        onOk={handleCreate}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="用户名" name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          
          <Form.Item label="邮箱" name="email" rules={[{ required: true, type: 'email', message: '请输入有效邮箱' }]}>
            <Input placeholder="email@example.com" />
          </Form.Item>
          
          <Form.Item label="密码" name="password" rules={[{ required: true, min: 8, message: '密码至少8位' }]}>
            <Input.Password placeholder="密码" />
          </Form.Item>
          
          <Form.Item label="显示名称" name="display_name">
            <Input placeholder="显示名称" />
          </Form.Item>
          
          <Form.Item label="角色" name="role" rules={[{ required: true }]}>
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
        title={`编辑用户: ${editModal.user?.display_name || editModal.user?.username}`}
        open={editModal.visible}
        onCancel={() => setEditModal({ visible: false, user: null })}
        onOk={handleUpdate}
      >
        <Form form={form} layout="vertical" initialValues={editModal.user || undefined}>
          <Form.Item label="显示名称" name="display_name">
            <Input placeholder="显示名称" />
          </Form.Item>
          
          <Form.Item label="邮箱" name="email" rules={[{ type: 'email', message: '请输入有效邮箱' }]}>
            <Input placeholder="email@example.com" />
          </Form.Item>
          
          <Form.Item label="角色" name="role" rules={[{ required: true }]}>
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

