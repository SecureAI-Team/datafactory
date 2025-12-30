import { Card, Row, Col, Statistic, Table, Tag, List, Typography } from 'antd'
import {
  FileTextOutlined,
  DatabaseOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons'

const { Title, Text } = Typography

// Mock data
const recentActivities = [
  { id: 1, type: 'success', message: 'Pipeline extract_to_silver 完成 (耗时 2m 15s)', time: '2分钟前' },
  { id: 2, type: 'info', message: '用户 张三 提交了新贡献: 华为案例.pdf', time: '5分钟前' },
  { id: 3, type: 'error', message: 'DQ 检查失败: KU-1234 缺少必填标签', time: '10分钟前' },
  { id: 4, type: 'success', message: '审核完成: 比亚迪方案.docx → 已发布', time: '15分钟前' },
  { id: 5, type: 'info', message: 'Pipeline ingest_to_bronze 开始处理 3 个文件', time: '20分钟前' },
]

const pendingReviews = [
  { id: 1, title: '华为PCB产线案例.pdf', contributor: '张三', type: '客户案例', created_at: '2024-01-20 14:30' },
  { id: 2, title: 'AOI选型话术补充.txt', contributor: '李明', type: '销售话术', created_at: '2024-01-20 10:15' },
  { id: 3, title: '客户成交案例卡', contributor: '王五', type: '现场信号', created_at: '2024-01-19 16:45' },
]

const columns = [
  { title: '标题', dataIndex: 'title', key: 'title' },
  { title: '贡献者', dataIndex: 'contributor', key: 'contributor' },
  { title: '类型', dataIndex: 'type', key: 'type', render: (type: string) => <Tag>{type}</Tag> },
  { title: '提交时间', dataIndex: 'created_at', key: 'created_at' },
]

export default function Dashboard() {
  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>仪表盘</Title>
      
      {/* Stats Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日处理"
              value={156}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#0ea5e9' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="KU 总量"
              value={2847}
              prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#22c55e' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="待审核"
              value={23}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#eab308' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="失败任务"
              value={5}
              prefix={<WarningOutlined />}
              valueStyle={{ color: '#ef4444' }}
            />
          </Card>
        </Col>
      </Row>
      
      {/* Main Content */}
      <Row gutter={[16, 16]}>
        <Col span={16}>
          {/* Pending Reviews */}
          <Card 
            title="待审核队列" 
            extra={<a href="/review">查看全部</a>}
            style={{ marginBottom: 16 }}
          >
            <Table 
              dataSource={pendingReviews} 
              columns={columns} 
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        
        <Col span={8}>
          {/* Recent Activity */}
          <Card title="最近活动">
            <List
              dataSource={recentActivities}
              renderItem={(item) => (
                <List.Item style={{ padding: '8px 0' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    {item.type === 'success' && <CheckCircleOutlined style={{ color: '#22c55e' }} />}
                    {item.type === 'info' && <SyncOutlined style={{ color: '#0ea5e9' }} />}
                    {item.type === 'error' && <WarningOutlined style={{ color: '#ef4444' }} />}
                    <div>
                      <Text style={{ fontSize: 13 }}>{item.message}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>{item.time}</Text>
                    </div>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

