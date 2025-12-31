import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Avatar, Dropdown, Button } from 'antd'
import {
  DashboardOutlined,
  FileSearchOutlined,
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
  ToolOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  CheckSquareOutlined,
  LineChartOutlined,
  MergeCellsOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'

const { Header, Sider, Content } = Layout

interface AdminLayoutProps {
  onLogout: () => void
}

const menuItems: MenuProps['items'] = [
  {
    key: '/',
    icon: <DashboardOutlined />,
    label: '仪表盘',
  },
  {
    key: '/review',
    icon: <FileSearchOutlined />,
    label: '贡献审核',
  },
  {
    key: '/dedup',
    icon: <MergeCellsOutlined />,
    label: '去重工作台',
  },
  {
    key: '/tasks',
    icon: <CheckSquareOutlined />,
    label: '任务协作',
  },
  {
    key: '/config',
    icon: <ToolOutlined />,
    label: '配置管理',
  },
  {
    key: '/quality',
    icon: <LineChartOutlined />,
    label: '质量分析',
  },
  {
    key: '/users',
    icon: <UserOutlined />,
    label: '用户管理',
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: '系统设置',
  },
]

export default function AdminLayout({ onLogout }: AdminLayoutProps) {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  
  const handleLogout = () => {
    localStorage.removeItem('admin_access_token')
    localStorage.removeItem('admin_refresh_token')
    onLogout()
    navigate('/login')
  }
  
  const userMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人信息',
      onClick: () => navigate('/settings'),
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
      onClick: handleLogout,
    },
  ]
  
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider 
        trigger={null} 
        collapsible 
        collapsed={collapsed}
        width={240}
        style={{
          borderRight: '1px solid #334155',
        }}
      >
        <div style={{ 
          height: 64, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          borderBottom: '1px solid #334155',
        }}>
          <div style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            background: 'linear-gradient(135deg, #0ea5e9, #d946ef)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <span style={{ color: 'white', fontWeight: 'bold' }}>AI</span>
          </div>
          {!collapsed && (
            <span style={{ marginLeft: 12, fontWeight: 600, fontSize: 16 }}>
              管理后台
            </span>
          )}
        </div>
        
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 'none' }}
        />
      </Sider>
      
      <Layout>
        <Header style={{ 
          padding: '0 24px', 
          background: '#1e293b',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #334155',
        }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 16, width: 48, height: 48 }}
          />
          
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar style={{ backgroundColor: '#0ea5e9' }}>A</Avatar>
              <span>管理员</span>
            </div>
          </Dropdown>
        </Header>
        
        <Content style={{ 
          margin: 24,
          padding: 24, 
          background: 'transparent',
          minHeight: 280,
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

