import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Layout,
  Menu,
  Table,
  Button,
  Space,
  Breadcrumb,
  Typography,
  Tag,
  Modal,
  Upload,
  Input,
  message,
  Dropdown,
  Tooltip,
  Spin,
  Empty,
  Card,
  Statistic,
  Row,
  Col,
  Popconfirm,
  Badge,
} from 'antd'
import {
  FolderOutlined,
  FileOutlined,
  UploadOutlined,
  FolderAddOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EyeOutlined,
  ReloadOutlined,
  InboxOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  ThunderboltOutlined,
  RestOutlined,
  CopyOutlined,
  ScissorOutlined,
  HomeOutlined,
  MoreOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { UploadFile, UploadProps } from 'antd/es/upload'
import { storageApi, StorageObject, BucketInfo } from '../api/storage'

const { Sider, Content } = Layout
const { Title, Text, Paragraph } = Typography
const { Dragger } = Upload

interface FileItem extends StorageObject {
  key: string
}

export default function Storage() {
  const queryClient = useQueryClient()
  
  // State
  const [selectedBucket, setSelectedBucket] = useState<string>('uploads')
  const [currentPath, setCurrentPath] = useState<string>('')
  const [selectedRows, setSelectedRows] = useState<FileItem[]>([])
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [newFolderModalVisible, setNewFolderModalVisible] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [previewModalVisible, setPreviewModalVisible] = useState(false)
  const [previewContent, setPreviewContent] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [processModalVisible, setProcessModalVisible] = useState(false)
  const [selectedDag, setSelectedDag] = useState('ingest_to_bronze')
  const [fileList, setFileList] = useState<UploadFile[]>([])
  
  // Queries
  const { data: buckets = [], isLoading: bucketsLoading } = useQuery({
    queryKey: ['storage-buckets'],
    queryFn: storageApi.listBuckets,
  })
  
  const { data: objectsData, isLoading: objectsLoading, refetch: refetchObjects } = useQuery({
    queryKey: ['storage-objects', selectedBucket, currentPath],
    queryFn: () => storageApi.listObjects(selectedBucket, currentPath),
    enabled: !!selectedBucket,
  })
  
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['storage-stats'],
    queryFn: storageApi.getStats,
  })
  
  // Mutations
  const uploadMutation = useMutation({
    mutationFn: ({ file }: { file: File }) =>
      storageApi.uploadObject(selectedBucket, file, currentPath),
    onSuccess: () => {
      message.success('文件上传成功')
      queryClient.invalidateQueries({ queryKey: ['storage-objects'] })
      queryClient.invalidateQueries({ queryKey: ['storage-stats'] })
      setUploadModalVisible(false)
      setFileList([])
    },
    onError: () => {
      message.error('文件上传失败')
    },
  })
  
  const createFolderMutation = useMutation({
    mutationFn: (name: string) => {
      const path = currentPath ? `${currentPath}${name}` : name
      return storageApi.createDirectory(selectedBucket, path)
    },
    onSuccess: () => {
      message.success('文件夹创建成功')
      queryClient.invalidateQueries({ queryKey: ['storage-objects'] })
      setNewFolderModalVisible(false)
      setNewFolderName('')
    },
    onError: () => {
      message.error('文件夹创建失败')
    },
  })
  
  const deleteMutation = useMutation({
    mutationFn: (paths: string[]) => storageApi.deleteObjects(selectedBucket, paths),
    onSuccess: (result) => {
      message.success(`已删除 ${result.deleted} 个对象`)
      queryClient.invalidateQueries({ queryKey: ['storage-objects'] })
      queryClient.invalidateQueries({ queryKey: ['storage-stats'] })
      setSelectedRows([])
    },
    onError: () => {
      message.error('删除失败')
    },
  })
  
  const trashMutation = useMutation({
    mutationFn: (paths: string[]) => storageApi.trashObjects(selectedBucket, paths),
    onSuccess: (result) => {
      message.success(`已移动 ${result.trashed} 个对象到垃圾箱`)
      queryClient.invalidateQueries({ queryKey: ['storage-objects'] })
      queryClient.invalidateQueries({ queryKey: ['storage-stats'] })
      setSelectedRows([])
    },
    onError: () => {
      message.error('移动到垃圾箱失败')
    },
  })
  
  const archiveMutation = useMutation({
    mutationFn: (paths: string[]) => storageApi.archiveObjects(selectedBucket, paths),
    onSuccess: (result) => {
      message.success(`已归档 ${result.archived} 个对象`)
      queryClient.invalidateQueries({ queryKey: ['storage-objects'] })
      queryClient.invalidateQueries({ queryKey: ['storage-stats'] })
      setSelectedRows([])
    },
    onError: () => {
      message.error('归档失败')
    },
  })
  
  const processMutation = useMutation({
    mutationFn: (data: { bucket: string; paths: string[]; dagId: string }) =>
      storageApi.processFiles(data.bucket, data.paths, data.dagId),
    onSuccess: (result) => {
      if (result.success) {
        message.success(result.message)
        setProcessModalVisible(false)
        setSelectedRows([])
      } else {
        message.error(result.message)
      }
    },
    onError: () => {
      message.error('处理请求失败')
    },
  })
  
  // Handlers
  const handleBucketSelect = useCallback((bucket: string) => {
    setSelectedBucket(bucket)
    setCurrentPath('')
    setSelectedRows([])
  }, [])
  
  const handleNavigate = useCallback((path: string) => {
    setCurrentPath(path)
    setSelectedRows([])
  }, [])
  
  const handleBreadcrumbClick = useCallback((index: number) => {
    const parts = currentPath.split('/').filter(Boolean)
    const newPath = parts.slice(0, index).join('/') + (index > 0 ? '/' : '')
    setCurrentPath(newPath)
    setSelectedRows([])
  }, [currentPath])
  
  const handleDownload = useCallback(async (path: string) => {
    try {
      const result = await storageApi.getDownloadUrl(selectedBucket, path)
      window.open(result.url, '_blank')
    } catch {
      message.error('获取下载链接失败')
    }
  }, [selectedBucket])
  
  const handlePreview = useCallback(async (path: string) => {
    setPreviewLoading(true)
    setPreviewModalVisible(true)
    try {
      const result = await storageApi.previewObject(selectedBucket, path)
      setPreviewContent(result.preview || result.message || '无法预览')
    } catch {
      setPreviewContent('预览失败')
    } finally {
      setPreviewLoading(false)
    }
  }, [selectedBucket])
  
  const handleUpload = useCallback(() => {
    if (fileList.length === 0) {
      message.warning('请选择要上传的文件')
      return
    }
    fileList.forEach((file) => {
      if (file.originFileObj) {
        uploadMutation.mutate({ file: file.originFileObj })
      }
    })
  }, [fileList, uploadMutation])
  
  const handleProcess = useCallback(() => {
    if (selectedRows.length === 0) {
      message.warning('请选择要处理的文件')
      return
    }
    processMutation.mutate({
      bucket: selectedBucket,
      paths: selectedRows.map((r) => r.path),
      dagId: selectedDag,
    })
  }, [selectedRows, selectedBucket, selectedDag, processMutation])
  
  // Format size
  const formatSize = (size: number): string => {
    if (size === 0) return '-'
    const units = ['B', 'KB', 'MB', 'GB']
    let unitIndex = 0
    let displaySize = size
    while (displaySize >= 1024 && unitIndex < units.length - 1) {
      displaySize /= 1024
      unitIndex++
    }
    return `${displaySize.toFixed(1)} ${units[unitIndex]}`
  }
  
  // Format date
  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    
    if (diff < 60000) return '刚刚'
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
    if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`
    
    return date.toLocaleDateString('zh-CN')
  }
  
  // Upload props
  const uploadProps: UploadProps = {
    multiple: true,
    fileList,
    beforeUpload: () => false,
    onChange: ({ fileList }) => setFileList(fileList),
  }
  
  // Table columns
  const columns: ColumnsType<FileItem> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: FileItem) => (
        <Space>
          {record.is_dir ? (
            <FolderOutlined style={{ color: '#faad14', fontSize: 18 }} />
          ) : (
            <FileOutlined style={{ color: '#1890ff', fontSize: 16 }} />
          )}
          {record.is_dir ? (
            <a onClick={() => handleNavigate(record.path)}>{name}</a>
          ) : (
            <span>
              {name}
              {record.is_new && (
                <Badge
                  status="success"
                  style={{ marginLeft: 8 }}
                  title="24小时内新增"
                />
              )}
            </span>
          )}
        </Space>
      ),
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: 100,
      render: (size: number) => formatSize(size),
    },
    {
      title: '修改时间',
      dataIndex: 'last_modified',
      key: 'last_modified',
      width: 120,
      render: (date: string | null) => formatDate(date),
    },
    {
      title: '类型',
      dataIndex: 'mime_type',
      key: 'mime_type',
      width: 150,
      render: (type: string | null, record: FileItem) =>
        record.is_dir ? (
          <Tag color="gold">文件夹</Tag>
        ) : (
          <Tag color="blue">{type?.split('/')[1] || '未知'}</Tag>
        ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_, record: FileItem) => (
        <Space size="small">
          {!record.is_dir && (
            <>
              <Tooltip title="预览">
                <Button
                  type="text"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => handlePreview(record.path)}
                />
              </Tooltip>
              <Tooltip title="下载">
                <Button
                  type="text"
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() => handleDownload(record.path)}
                />
              </Tooltip>
            </>
          )}
          <Dropdown
            menu={{
              items: [
                {
                  key: 'trash',
                  label: '移到垃圾箱',
                  icon: <RestOutlined />,
                  onClick: () => trashMutation.mutate([record.path]),
                },
                {
                  key: 'archive',
                  label: '归档',
                  icon: <InboxOutlined />,
                  onClick: () => archiveMutation.mutate([record.path]),
                },
                {
                  type: 'divider',
                },
                {
                  key: 'delete',
                  label: '永久删除',
                  icon: <DeleteOutlined />,
                  danger: true,
                  onClick: () => {
                    Modal.confirm({
                      title: '确认删除',
                      content: `确定要永久删除 "${record.name}" 吗？此操作不可恢复。`,
                      okText: '删除',
                      okType: 'danger',
                      cancelText: '取消',
                      onOk: () => deleteMutation.mutate([record.path]),
                    })
                  },
                },
              ],
            }}
            trigger={['click']}
          >
            <Button type="text" size="small" icon={<MoreOutlined />} />
          </Dropdown>
        </Space>
      ),
    },
  ]
  
  // Prepare table data
  const tableData: FileItem[] = (objectsData?.objects || []).map((obj) => ({
    ...obj,
    key: obj.path,
  }))
  
  // Breadcrumb items
  const breadcrumbItems = [
    { title: <HomeOutlined />, onClick: () => handleBreadcrumbClick(0) },
    { title: selectedBucket },
    ...currentPath.split('/').filter(Boolean).map((part, index) => ({
      title: part,
      onClick: () => handleBreadcrumbClick(index + 1),
    })),
  ]
  
  // Bucket menu items
  const bucketMenuItems = buckets.map((bucket: BucketInfo) => ({
    key: bucket.name,
    icon: bucket.name === 'trash' ? <RestOutlined /> :
          bucket.name === 'archive' ? <InboxOutlined /> :
          <DatabaseOutlined />,
    label: (
      <span>
        {bucket.name}
        {bucket.name === selectedBucket && <Badge status="processing" style={{ marginLeft: 8 }} />}
      </span>
    ),
  }))
  
  // DAG options for processing
  const dagOptions = [
    { value: 'ingest_to_bronze', label: '原始入库 (Ingest)' },
    { value: 'extract_to_silver', label: '解析提取 (Extract)' },
    { value: 'expand_to_gold', label: '扩展增强 (Expand)' },
    { value: 'index_to_opensearch', label: '索引更新 (Index)' },
  ]
  
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={2} style={{ marginBottom: 0 }}>
          <CloudServerOutlined style={{ marginRight: 8 }} />
          存储管理
        </Title>
        <Space>
          <Button
            icon={<FolderAddOutlined />}
            onClick={() => setNewFolderModalVisible(true)}
          >
            新建文件夹
          </Button>
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={() => setUploadModalVisible(true)}
          >
            上传文件
          </Button>
        </Space>
      </div>
      
      {/* Stats Cards */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Bucket 数量"
              value={stats?.buckets?.length || 0}
              loading={statsLoading}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="文件总数"
              value={stats?.total_objects || 0}
              loading={statsLoading}
              prefix={<FileOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="存储容量"
              value={formatSize(stats?.total_size || 0)}
              loading={statsLoading}
              prefix={<CloudServerOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="新文件 (24h)"
              value={stats?.new_files_count || 0}
              loading={statsLoading}
              valueStyle={{ color: '#52c41a' }}
              prefix={<Badge status="success" />}
            />
          </Card>
        </Col>
      </Row>
      
      <Layout style={{ background: '#fff', border: '1px solid #f0f0f0', borderRadius: 8 }}>
        {/* Bucket Sidebar */}
        <Sider
          width={200}
          style={{
            background: '#fafafa',
            borderRight: '1px solid #f0f0f0',
            borderRadius: '8px 0 0 8px',
          }}
        >
          <div style={{ padding: '16px 8px 8px 8px' }}>
            <Text type="secondary" style={{ fontSize: 12, paddingLeft: 8 }}>BUCKETS</Text>
          </div>
          {bucketsLoading ? (
            <div style={{ textAlign: 'center', padding: 20 }}><Spin /></div>
          ) : (
            <Menu
              mode="inline"
              selectedKeys={[selectedBucket]}
              items={bucketMenuItems}
              onClick={({ key }) => handleBucketSelect(key)}
              style={{ background: 'transparent', border: 'none' }}
            />
          )}
        </Sider>
        
        {/* File List Content */}
        <Content style={{ padding: 16, minHeight: 400 }}>
          {/* Breadcrumb & Actions */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Breadcrumb items={breadcrumbItems} />
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => refetchObjects()}
                loading={objectsLoading}
              >
                刷新
              </Button>
              {selectedRows.length > 0 && (
                <Dropdown
                  menu={{
                    items: [
                      {
                        key: 'process',
                        label: '处理选中文件',
                        icon: <ThunderboltOutlined />,
                        onClick: () => setProcessModalVisible(true),
                      },
                      {
                        key: 'trash',
                        label: '移到垃圾箱',
                        icon: <RestOutlined />,
                        onClick: () => trashMutation.mutate(selectedRows.map((r) => r.path)),
                      },
                      {
                        key: 'archive',
                        label: '归档',
                        icon: <InboxOutlined />,
                        onClick: () => archiveMutation.mutate(selectedRows.map((r) => r.path)),
                      },
                      { type: 'divider' },
                      {
                        key: 'delete',
                        label: '永久删除',
                        icon: <DeleteOutlined />,
                        danger: true,
                        onClick: () => {
                          Modal.confirm({
                            title: '确认删除',
                            content: `确定要永久删除选中的 ${selectedRows.length} 个对象吗？`,
                            okText: '删除',
                            okType: 'danger',
                            cancelText: '取消',
                            onOk: () => deleteMutation.mutate(selectedRows.map((r) => r.path)),
                          })
                        },
                      },
                    ],
                  }}
                >
                  <Button type="primary">
                    批量操作 ({selectedRows.length})
                  </Button>
                </Dropdown>
              )}
            </Space>
          </div>
          
          {/* File Table */}
          {objectsLoading ? (
            <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
          ) : tableData.length === 0 ? (
            <Empty
              description="此目录为空"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            >
              <Space>
                <Button onClick={() => setUploadModalVisible(true)} icon={<UploadOutlined />}>
                  上传文件
                </Button>
                <Button onClick={() => setNewFolderModalVisible(true)} icon={<FolderAddOutlined />}>
                  创建文件夹
                </Button>
              </Space>
            </Empty>
          ) : (
            <Table
              columns={columns}
              dataSource={tableData}
              rowSelection={{
                selectedRowKeys: selectedRows.map((r) => r.key),
                onChange: (_, rows) => setSelectedRows(rows),
              }}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 项`,
              }}
              size="middle"
            />
          )}
        </Content>
      </Layout>
      
      {/* Upload Modal */}
      <Modal
        title="上传文件"
        open={uploadModalVisible}
        onOk={handleUpload}
        onCancel={() => {
          setUploadModalVisible(false)
          setFileList([])
        }}
        confirmLoading={uploadMutation.isPending}
        okText="上传"
        cancelText="取消"
        width={600}
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">
            目标位置: {selectedBucket}/{currentPath || '(根目录)'}
          </Text>
        </div>
        <Dragger {...uploadProps}>
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">支持单个或批量上传</p>
        </Dragger>
      </Modal>
      
      {/* New Folder Modal */}
      <Modal
        title="新建文件夹"
        open={newFolderModalVisible}
        onOk={() => createFolderMutation.mutate(newFolderName)}
        onCancel={() => {
          setNewFolderModalVisible(false)
          setNewFolderName('')
        }}
        confirmLoading={createFolderMutation.isPending}
        okText="创建"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">
            位置: {selectedBucket}/{currentPath || '(根目录)'}
          </Text>
        </div>
        <Input
          placeholder="请输入文件夹名称"
          value={newFolderName}
          onChange={(e) => setNewFolderName(e.target.value)}
          onPressEnter={() => createFolderMutation.mutate(newFolderName)}
        />
      </Modal>
      
      {/* Preview Modal */}
      <Modal
        title="文件预览"
        open={previewModalVisible}
        onCancel={() => {
          setPreviewModalVisible(false)
          setPreviewContent(null)
        }}
        footer={null}
        width={800}
      >
        {previewLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : (
          <pre
            style={{
              maxHeight: 500,
              overflow: 'auto',
              background: '#f5f5f5',
              padding: 16,
              borderRadius: 4,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {previewContent}
          </pre>
        )}
      </Modal>
      
      {/* Process Modal */}
      <Modal
        title="处理文件"
        open={processModalVisible}
        onOk={handleProcess}
        onCancel={() => setProcessModalVisible(false)}
        confirmLoading={processMutation.isPending}
        okText="开始处理"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <Text strong>已选择 {selectedRows.length} 个文件</Text>
          <ul style={{ marginTop: 8, maxHeight: 150, overflow: 'auto' }}>
            {selectedRows.slice(0, 10).map((r) => (
              <li key={r.key}>{r.name}</li>
            ))}
            {selectedRows.length > 10 && <li>...还有 {selectedRows.length - 10} 个</li>}
          </ul>
        </div>
        <div>
          <Text type="secondary">选择处理流程:</Text>
          <div style={{ marginTop: 8 }}>
            {dagOptions.map((opt) => (
              <Tag.CheckableTag
                key={opt.value}
                checked={selectedDag === opt.value}
                onChange={() => setSelectedDag(opt.value)}
                style={{ marginBottom: 8, padding: '4px 12px' }}
              >
                {opt.label}
              </Tag.CheckableTag>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  )
}

