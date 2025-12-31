import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useMutation } from '@tanstack/react-query'
import { 
  Upload as UploadIcon, 
  FileText, 
  X, 
  CheckCircle, 
  AlertCircle,
  ArrowLeft,
  Loader2
} from 'lucide-react'
import { contributeApi } from '../api/contribute'
import clsx from 'clsx'

interface UploadingFile {
  file: File
  progress: number
  status: 'uploading' | 'success' | 'error'
  error?: string
}

const kuTypeOptions = [
  { value: 'core.product_feature', label: '产品功能说明', category: 'product' },
  { value: 'core.tech_spec', label: '技术规格', category: 'product' },
  { value: 'solution.industry', label: '行业解决方案', category: 'solution' },
  { value: 'solution.proposal', label: '方案书', category: 'solution' },
  { value: 'case.customer_story', label: '客户案例', category: 'case' },
  { value: 'case.public_reference', label: '公开证据', category: 'case' },
  { value: 'quote.pricebook', label: '报价单', category: 'quote' },
  { value: 'sales.playbook', label: '销售话术', category: 'sales' },
  { value: 'delivery.sop', label: '交付SOP', category: 'delivery' },
  { value: 'support.troubleshooting', label: '故障排查', category: 'delivery' },
]

// Allowed MIME types for file upload - used in dropzone accept config
const ALLOWED_MIME_TYPES = {
  'application/pdf': ['.pdf'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.ms-powerpoint': ['.ppt'],
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
  'text/csv': ['.csv'],
}

export default function Upload() {
  const navigate = useNavigate()
  const [files, setFiles] = useState<UploadingFile[]>([])
  const [kuType, setKuType] = useState('core.product_feature')
  const [description, setDescription] = useState('')
  const [visibility, setVisibility] = useState('internal')
  
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      return contributeApi.uploadFile(file, {
        title: file.name,
        description: description || undefined,
        ku_type_code: kuType,
        visibility,
      })
    },
  })
  
  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles = acceptedFiles.map(file => ({
      file,
      progress: 0,
      status: 'uploading' as const,
    }))
    setFiles(prev => [...prev, ...newFiles])
    
    // Upload each file
    acceptedFiles.forEach((file) => {
      uploadMutation.mutate(file, {
        onSuccess: () => {
          setFiles(prev => prev.map(f => 
            f.file === file 
              ? { ...f, progress: 100, status: 'success' } 
              : f
          ))
        },
        onError: (error) => {
          setFiles(prev => prev.map(f => 
            f.file === file 
              ? { ...f, status: 'error', error: (error as Error).message } 
              : f
          ))
        },
      })
    })
  }, [kuType, description, visibility, uploadMutation])
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ALLOWED_MIME_TYPES,
    maxSize: 50 * 1024 * 1024, // 50MB
  })
  
  const removeFile = (file: File) => {
    setFiles(prev => prev.filter(f => f.file !== file))
  }
  
  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase()
    const colors: Record<string, string> = {
      pdf: 'text-red-400',
      doc: 'text-blue-400',
      docx: 'text-blue-400',
      ppt: 'text-orange-400',
      pptx: 'text-orange-400',
      xls: 'text-green-400',
      xlsx: 'text-green-400',
      txt: 'text-gray-400',
      md: 'text-purple-400',
      csv: 'text-teal-400',
    }
    return <FileText className={clsx('w-5 h-5', colors[ext || ''] || 'text-gray-400')} />
  }
  
  const successCount = files.filter(f => f.status === 'success').length
  const errorCount = files.filter(f => f.status === 'error').length
  const uploadingCount = files.filter(f => f.status === 'uploading').length
  
  return (
    <div className="min-h-screen bg-slate-900 py-8 px-4">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <button 
            onClick={() => navigate('/')}
            className="p-2 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold">快速上传</h1>
            <p className="text-slate-400 text-sm">上传文件贡献到知识库</p>
          </div>
        </div>
        
        {/* Upload Options */}
        <div className="bg-slate-800/50 rounded-xl p-6 mb-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              KU 类型
            </label>
            <select
              value={kuType}
              onChange={(e) => setKuType(e.target.value)}
              className="w-full px-4 py-2.5 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              {kuTypeOptions.map(opt => (
                <option key={opt.value} value={opt.value}>
                  [{opt.category}] {opt.label}
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              描述 (可选)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="简要描述文件内容..."
              rows={2}
              className="w-full px-4 py-2.5 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 resize-none"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              可见性
            </label>
            <div className="flex gap-3">
              {[
                { value: 'internal', label: '内部可见' },
                { value: 'public', label: '公开' },
                { value: 'confidential', label: '机密' },
              ].map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setVisibility(opt.value)}
                  className={clsx(
                    'px-4 py-2 rounded-lg border transition-colors',
                    visibility === opt.value
                      ? 'bg-sky-500/20 border-sky-500 text-sky-400'
                      : 'bg-slate-700 border-slate-600 text-slate-300 hover:border-slate-500'
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        
        {/* Drop Zone */}
        <div
          {...getRootProps()}
          className={clsx(
            'border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all',
            isDragActive
              ? 'border-sky-500 bg-sky-500/10'
              : 'border-slate-600 hover:border-slate-500 hover:bg-slate-800/30'
          )}
        >
          <input {...getInputProps()} />
          <UploadIcon className="w-12 h-12 mx-auto mb-4 text-slate-400" />
          {isDragActive ? (
            <p className="text-lg text-sky-400">放开以上传文件...</p>
          ) : (
            <>
              <p className="text-lg text-slate-300 mb-2">点击或拖拽文件到此处</p>
              <p className="text-sm text-slate-500">
                支持 PDF, Word, PPT, Excel, TXT, Markdown, CSV (最大 50MB)
              </p>
            </>
          )}
        </div>
        
        {/* File List */}
        {files.length > 0 && (
          <div className="mt-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium">
                上传列表 
                <span className="text-slate-400 ml-2">
                  ({successCount} 成功, {uploadingCount} 上传中, {errorCount} 失败)
                </span>
              </h3>
              {files.length > 0 && (
                <button
                  onClick={() => setFiles([])}
                  className="text-sm text-slate-400 hover:text-white"
                >
                  清空列表
                </button>
              )}
            </div>
            
            <div className="space-y-2">
              {files.map((f, index) => (
                <div 
                  key={`${f.file.name}-${index}`}
                  className="flex items-center gap-3 p-3 bg-slate-800/50 rounded-lg"
                >
                  {getFileIcon(f.file.name)}
                  <div className="flex-1 min-w-0">
                    <p className="truncate text-sm">{f.file.name}</p>
                    <p className="text-xs text-slate-500">
                      {(f.file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  {f.status === 'uploading' && (
                    <Loader2 className="w-5 h-5 text-sky-400 animate-spin" />
                  )}
                  {f.status === 'success' && (
                    <CheckCircle className="w-5 h-5 text-green-400" />
                  )}
                  {f.status === 'error' && (
                    <div className="flex items-center gap-2">
                      <AlertCircle className="w-5 h-5 text-red-400" />
                      <button
                        onClick={() => removeFile(f.file)}
                        className="p-1 hover:bg-slate-700 rounded"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Tips */}
        <div className="mt-8 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg">
          <p className="text-amber-300 text-sm">
            💡 提示：上传的文件将进入审核队列，审核通过后会自动入库到知识库中。
            您可以在「我的资料」中查看上传状态和审核结果。
          </p>
        </div>
      </div>
    </div>
  )
}

