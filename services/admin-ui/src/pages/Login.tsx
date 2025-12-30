import { useState } from 'react'
import { Form, Input, Button, Card, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import axios from 'axios'

interface LoginProps {
  onLogin: () => void
}

export default function Login({ onLogin }: LoginProps) {
  const [loading, setLoading] = useState(false)
  
  const handleSubmit = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const response = await axios.post('/api/auth/login', values)
      const { access_token, refresh_token, user } = response.data
      
      // Check if user is admin
      if (user.role !== 'admin' && user.role !== 'data_ops') {
        message.error('您没有管理后台访问权限')
        return
      }
      
      localStorage.setItem('admin_access_token', access_token)
      localStorage.setItem('admin_refresh_token', refresh_token)
      localStorage.setItem('admin_user', JSON.stringify(user))
      
      message.success('登录成功')
      onLogin()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)',
    }}>
      <Card
        style={{
          width: 400,
          background: 'rgba(30, 41, 59, 0.9)',
          border: '1px solid #334155',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 64,
            height: 64,
            borderRadius: 16,
            background: 'linear-gradient(135deg, #0ea5e9, #d946ef)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 16,
          }}>
            <span style={{ color: 'white', fontWeight: 'bold', fontSize: 24 }}>AI</span>
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>管理后台</h1>
          <p style={{ color: '#94a3b8', marginTop: 8 }}>AI 数据工厂</p>
        </div>
        
        <Form
          name="login"
          onFinish={handleSubmit}
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input 
              prefix={<UserOutlined />} 
              placeholder="用户名 / 邮箱" 
            />
          </Form.Item>
          
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password 
              prefix={<LockOutlined />} 
              placeholder="密码" 
            />
          </Form.Item>
          
          <Form.Item>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading}
              block
            >
              登录
            </Button>
          </Form.Item>
        </Form>
        
        <p style={{ textAlign: 'center', color: '#64748b', fontSize: 12 }}>
          仅限管理员和数据运维人员登录
        </p>
      </Card>
    </div>
  )
}

