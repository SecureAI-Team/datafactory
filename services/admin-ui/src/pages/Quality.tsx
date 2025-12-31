import { Card, Typography, Table, Row, Col, Statistic, Progress, Spin, Tag, Tabs } from 'antd'
import { 
  CheckCircleOutlined, 
  ExclamationCircleOutlined, 
  LineChartOutlined,
  ThunderboltOutlined 
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { statsApi } from '../api'

const { Title, Text } = Typography

function QualityOverview() {
  const { data: qualityData, isLoading } = useQuery({
    queryKey: ['quality-stats'],
    queryFn: () => statsApi.getQuality(),
  })
  
  return (
    <Spin spinning={isLoading}>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic 
              title="DQ 通过率" 
              value={qualityData?.dq_pass_rate || 0} 
              suffix="%" 
              precision={1}
              valueStyle={{ color: (qualityData?.dq_pass_rate || 0) >= 80 ? '#22c55e' : '#ef4444' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="总 DQ 运行次数" 
              value={qualityData?.total_dq_runs || 0}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="KU 类型数" 
              value={Object.keys(qualityData?.ku_type_distribution || {}).length}
              prefix={<LineChartOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="已发布 KU" 
              value={qualityData?.ku_status_distribution?.published || 0}
              valueStyle={{ color: '#22c55e' }}
            />
          </Card>
        </Col>
      </Row>
      
      <Row gutter={16}>
        <Col span={12}>
          <Card title="KU 类型分布">
            {qualityData?.ku_type_distribution && Object.keys(qualityData.ku_type_distribution).length > 0 ? (
              <div>
                {Object.entries(qualityData.ku_type_distribution).map(([type, count]) => (
                  <div key={type} style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text>{type}</Text>
                      <Text strong>{count as number}</Text>
                    </div>
                    <Progress 
                      percent={Math.round((count as number) / Object.values(qualityData.ku_type_distribution).reduce((a, b) => (a as number) + (b as number), 0) * 100)} 
                      showInfo={false}
                      strokeColor="#3b82f6"
                    />
                  </div>
                ))}
              </div>
            ) : (
              <Text type="secondary">暂无数据</Text>
            )}
          </Card>
        </Col>
        <Col span={12}>
          <Card title="KU 状态分布">
            {qualityData?.ku_status_distribution && Object.keys(qualityData.ku_status_distribution).length > 0 ? (
              <div>
                {Object.entries(qualityData.ku_status_distribution).map(([status, count]) => {
                  const colors: Record<string, string> = {
                    published: '#22c55e',
                    draft: '#eab308',
                    pending: '#3b82f6',
                    rejected: '#ef4444',
                  }
                  return (
                    <div key={status} style={{ marginBottom: 12 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Text>{status}</Text>
                        <Text strong>{count as number}</Text>
                      </div>
                      <Progress 
                        percent={Math.round((count as number) / Object.values(qualityData.ku_status_distribution).reduce((a, b) => (a as number) + (b as number), 0) * 100)} 
                        showInfo={false}
                        strokeColor={colors[status] || '#64748b'}
                      />
                    </div>
                  )
                })}
              </div>
            ) : (
              <Text type="secondary">暂无数据</Text>
            )}
          </Card>
        </Col>
      </Row>
    </Spin>
  )
}

function FeedbackAnalysis() {
  // Placeholder for feedback analysis
  const mockFeedback = [
    { query: 'AOI8000 精度是多少？', feedback: 'positive', reason: '答案准确', date: '2024-01-20' },
    { query: '有没有汽车行业案例？', feedback: 'negative', reason: '找不到相关案例', date: '2024-01-19' },
    { query: '产品报价单在哪？', feedback: 'negative', reason: '回答不完整', date: '2024-01-18' },
  ]
  
  const columns = [
    { title: '问题', dataIndex: 'query', key: 'query', ellipsis: true },
    { 
      title: '反馈', 
      dataIndex: 'feedback', 
      key: 'feedback',
      render: (fb: string) => (
        <Tag color={fb === 'positive' ? 'green' : 'red'}>
          {fb === 'positive' ? '👍 有帮助' : '👎 没帮助'}
        </Tag>
      ),
    },
    { title: '原因', dataIndex: 'reason', key: 'reason' },
    { title: '日期', dataIndex: 'date', key: 'date' },
    {
      title: '操作',
      key: 'actions',
      render: () => <a>创建优化任务</a>,
    },
  ]
  
  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic title="正面反馈" value={85} suffix="%" valueStyle={{ color: '#22c55e' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="负面反馈" value={15} suffix="%" valueStyle={{ color: '#ef4444' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="待处理反馈" value={12} />
          </Card>
        </Col>
      </Row>
      
      <Card title="负面反馈列表">
        <Table 
          dataSource={mockFeedback.filter(f => f.feedback === 'negative')} 
          columns={columns} 
          rowKey="query"
          pagination={false}
        />
      </Card>
    </div>
  )
}

function DQReport() {
  // Placeholder for DQ report
  const mockDQRuns = [
    { id: 1, ku_id: 'KU-1234', passed: false, reasons: ['缺少必填标签'], date: '2024-01-20 10:30' },
    { id: 2, ku_id: 'KU-1235', passed: true, reasons: [], date: '2024-01-20 09:15' },
    { id: 3, ku_id: 'KU-1236', passed: false, reasons: ['内容长度不足'], date: '2024-01-19 16:45' },
  ]
  
  const columns = [
    { title: 'KU ID', dataIndex: 'ku_id', key: 'ku_id' },
    { 
      title: '结果', 
      dataIndex: 'passed', 
      key: 'passed',
      render: (passed: boolean) => (
        passed ? 
          <Tag color="green" icon={<CheckCircleOutlined />}>通过</Tag> :
          <Tag color="red" icon={<ExclamationCircleOutlined />}>失败</Tag>
      ),
    },
    { 
      title: '失败原因', 
      dataIndex: 'reasons', 
      key: 'reasons',
      render: (reasons: string[]) => reasons.length > 0 ? reasons.join(', ') : '-',
    },
    { title: '时间', dataIndex: 'date', key: 'date' },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: { passed: boolean }) => (
        record.passed ? '-' : <a>查看详情</a>
      ),
    },
  ]
  
  return (
    <div>
      <Card title="DQ 检查记录" extra={<a>查看全部</a>}>
        <Table 
          dataSource={mockDQRuns} 
          columns={columns} 
          rowKey="id"
          pagination={false}
        />
      </Card>
    </div>
  )
}

function RegressionTest() {
  // Placeholder for regression testing
  return (
    <div>
      <Card>
        <div style={{ textAlign: 'center', padding: 40 }}>
          <ExclamationCircleOutlined style={{ fontSize: 48, color: '#64748b', marginBottom: 16 }} />
          <Title level={4} type="secondary">回归测试功能待实现</Title>
          <Text type="secondary">
            计划功能：多轮对话回归测试、答案质量评估、自动化测试用例管理
          </Text>
        </div>
      </Card>
    </div>
  )
}

export default function Quality() {
  const tabItems = [
    { key: 'overview', label: '质量概览', children: <QualityOverview /> },
    { key: 'feedback', label: '反馈分析', children: <FeedbackAnalysis /> },
    { key: 'dq', label: 'DQ 报告', children: <DQReport /> },
    { key: 'regression', label: '回归测试', children: <RegressionTest /> },
  ]
  
  return (
    <div>
      <Title level={2} style={{ marginBottom: 24 }}>质量分析</Title>
      
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  )
}

