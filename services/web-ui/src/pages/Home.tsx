import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Send,
  ThumbsUp,
  ThumbsDown,
  Copy,
  Share2,
  Loader2,
  BookOpen,
  Calculator,
  FileText,
  Users,
  MessageSquare,
  Zap,
  Upload,
  PenLine,
  X,
  Pencil,
  Check,
} from 'lucide-react'
import { useNavigate as useRouterNavigate } from 'react-router-dom'
import { conversationsApi } from '../api/conversations'
import { contributeApi } from '../api/contribute'
import { useConversationStore, Message } from '../store/conversationStore'
import MarkdownRenderer from '../components/MarkdownRenderer'
import clsx from 'clsx'

// Patterns that indicate missing information
const MISSING_INFO_PATTERNS = [
  '抱歉',
  '暂未找到',
  '没有找到',
  '暂无相关',
  '无法找到',
  '找不到',
  '暂时没有',
  '缺少相关',
]

// Patterns that indicate high-value signals
const HIGH_VALUE_PATTERNS = [
  '成交',
  '签约',
  '中标',
  '选择了我们',
  '合作成功',
  '客户很满意',
]

// 快捷场景卡片
const scenarios = [
  { id: 'param', icon: BookOpen, label: '参数查询', color: 'primary' },
  { id: 'case', icon: Users, label: '案例检索', color: 'green' },
  { id: 'quote', icon: Calculator, label: '报价测算', color: 'yellow' },
  { id: 'solution', icon: FileText, label: '方案生成', color: 'blue' },
  { id: 'compare', icon: Zap, label: '对比分析', color: 'purple' },
  { id: 'talk', icon: MessageSquare, label: '话术应对', color: 'pink' },
]

interface MessageItemProps {
  message: Message
  onFeedback: (feedback: 'positive' | 'negative') => void
  onEdit?: (messageId: string, newContent: string) => void
  conversationId?: string
  userQuery?: string
  canEdit?: boolean
}

// Embedded Contribution Prompt Component
function ContributionPrompt({ 
  type, 
  onClose, 
  conversationId,
  queryText
}: { 
  type: 'missing_info' | 'high_value_signal'
  onClose: () => void
  conversationId?: string
  queryText?: string
}) {
  const nav = useRouterNavigate()
  const [draftMode, setDraftMode] = useState(false)
  const [draftContent, setDraftContent] = useState('')
  const [customerName, setCustomerName] = useState('')
  
  const handleFileUpload = () => {
    nav('/upload')
  }
  
  const handleSaveDraft = async () => {
    if (!draftContent.trim()) return
    try {
      await contributeApi.saveDraft({
        title: customerName || '草稿知识',
        description: draftContent,
        ku_type_code: type === 'high_value_signal' ? 'case.customer_story' : 'field.signal',
        trigger_type: type,
        conversation_id: conversationId,
        query_text: queryText,
      })
      setDraftMode(false)
      setDraftContent('')
      setCustomerName('')
      onClose()
      // Show success message
      alert('已保存到贡献队列，等待审核')
    } catch (error) {
      console.error('Save draft failed:', error)
      alert('保存失败，请稍后重试')
    }
  }
  
  if (type === 'missing_info') {
    return (
      <div className="mt-4 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg animate-fade-in">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2 text-amber-400">
            <span>💡</span>
            <span className="font-medium">您手上有相关材料吗？</span>
          </div>
          <button onClick={onClose} className="text-dark-400 hover:text-white">
            <X size={16} />
          </button>
        </div>
        
        {!draftMode ? (
          <>
            <p className="text-sm text-dark-300 mb-3">
              上传相关文件或描述您了解的信息，帮助丰富知识库：
            </p>
            <div className="flex gap-2">
              <button 
                onClick={handleFileUpload}
                className="flex-1 btn-ghost py-2 border border-dashed border-dark-600 hover:border-primary-500"
              >
                <Upload size={16} className="mr-2" />
                上传文件
              </button>
              <button 
                onClick={() => setDraftMode(true)}
                className="flex-1 btn-ghost py-2 border border-dashed border-dark-600 hover:border-primary-500"
              >
                <PenLine size={16} className="mr-2" />
                描述信息
              </button>
            </div>
          </>
        ) : (
          <div className="space-y-3">
            <textarea
              value={draftContent}
              onChange={(e) => setDraftContent(e.target.value)}
              placeholder="描述您了解的相关信息..."
              className="w-full bg-dark-800 border border-dark-600 rounded-lg p-3 text-sm resize-none h-24 focus:border-primary-500 focus:outline-none"
            />
            <div className="flex gap-2">
              <button 
                onClick={() => setDraftMode(false)}
                className="btn-ghost py-1.5 px-4 text-sm"
              >
                取消
              </button>
              <button 
                onClick={handleSaveDraft}
                disabled={!draftContent.trim()}
                className="btn-primary py-1.5 px-4 text-sm"
              >
                保存草稿
              </button>
            </div>
          </div>
        )}
      </div>
    )
  }
  
  // High value signal prompt
  return (
    <div className="mt-4 p-4 bg-green-500/10 border border-green-500/30 rounded-lg animate-fade-in">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 text-green-400">
          <span>🎉</span>
          <span className="font-medium">是否将此成功案例保存到知识库？</span>
        </div>
        <button onClick={onClose} className="text-dark-400 hover:text-white">
          <X size={16} />
        </button>
      </div>
      
      <div className="space-y-3">
        <input
          type="text"
          value={customerName}
          onChange={(e) => setCustomerName(e.target.value)}
          placeholder="客户名称（可选）"
          className="w-full bg-dark-800 border border-dark-600 rounded-lg p-2 text-sm focus:border-primary-500 focus:outline-none"
        />
        <textarea
          value={draftContent}
          onChange={(e) => setDraftContent(e.target.value)}
          placeholder="补充案例要点..."
          className="w-full bg-dark-800 border border-dark-600 rounded-lg p-3 text-sm resize-none h-20 focus:border-primary-500 focus:outline-none"
        />
        <div className="flex gap-2">
          <button 
            onClick={onClose}
            className="btn-ghost py-1.5 px-4 text-sm"
          >
            稍后再说
          </button>
          <button 
            onClick={handleSaveDraft}
            className="btn-primary py-1.5 px-4 text-sm"
          >
            保存案例
          </button>
        </div>
      </div>
    </div>
  )
}

function MessageItem({ message, onFeedback, onEdit, conversationId, userQuery, canEdit }: MessageItemProps) {
  const [copied, setCopied] = useState(false)
  const [showContribution, setShowContribution] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState(message.content)
  // Share dialog state - reserved for future use
  const [, setShareDialogOpen] = useState(false)
  
  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  
  const handleShare = async () => {
    if (conversationId) {
      try {
        const result = await conversationsApi.createShare(conversationId)
        navigator.clipboard.writeText(result.share_url)
        setShareDialogOpen(false)
        alert('分享链接已复制到剪贴板')
      } catch (error) {
        console.error('Share failed:', error)
      }
    }
  }
  
  const handleStartEdit = () => {
    setEditContent(message.content)
    setIsEditing(true)
  }
  
  const handleCancelEdit = () => {
    setEditContent(message.content)
    setIsEditing(false)
  }
  
  const handleConfirmEdit = () => {
    if (editContent.trim() && editContent !== message.content && onEdit) {
      onEdit(message.message_id, editContent.trim())
    }
    setIsEditing(false)
  }
  
  const handleEditKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleConfirmEdit()
    } else if (e.key === 'Escape') {
      handleCancelEdit()
    }
  }
  
  // Detect if this is a "missing info" response
  const isMissingInfo = message.role === 'assistant' && 
    MISSING_INFO_PATTERNS.some(pattern => message.content.includes(pattern))
  
  // Detect high-value signal in user message
  const isHighValueSignal = message.role === 'user' &&
    HIGH_VALUE_PATTERNS.some(pattern => message.content.includes(pattern))
  
  return (
    <div
      className={clsx(
        'flex gap-3 animate-fade-in group',
        message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <div
        className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
          message.role === 'user' ? 'bg-primary-600' : 'bg-dark-700'
        )}
      >
        {message.role === 'user' ? (
          <span className="text-white text-sm">👤</span>
        ) : (
          <span className="text-lg">🤖</span>
        )}
      </div>
      
      {/* Message Content */}
      <div
        className={clsx(
          'max-w-[75%] p-4',
          message.role === 'user' ? 'message-user' : 'message-assistant'
        )}
      >
        {/* Edit Mode */}
        {isEditing ? (
          <div className="space-y-2">
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              onKeyDown={handleEditKeyDown}
              className="w-full bg-dark-700 border border-dark-500 rounded-lg p-3 text-sm resize-none min-h-[80px] focus:border-primary-500 focus:outline-none text-dark-100"
              autoFocus
            />
            <div className="flex items-center gap-2 justify-end">
              <button
                onClick={handleCancelEdit}
                className="btn-ghost py-1 px-3 text-xs flex items-center gap-1"
              >
                <X size={14} />
                取消
              </button>
              <button
                onClick={handleConfirmEdit}
                className="btn-primary py-1 px-3 text-xs flex items-center gap-1"
                disabled={!editContent.trim() || editContent === message.content}
              >
                <Check size={14} />
                确认
              </button>
            </div>
          </div>
        ) : (
          <MarkdownRenderer content={message.content} />
        )}
        
        {/* Sources */}
        {!isEditing && message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-dark-700">
            <p className="text-xs text-dark-400 mb-1">📎 来源：</p>
            <div className="flex flex-wrap gap-2">
              {message.sources.map((source, idx) => (
                <span
                  key={idx}
                  className="text-xs bg-dark-700 px-2 py-1 rounded text-primary-400"
                >
                  {source.title}
                </span>
              ))}
            </div>
          </div>
        )}
        
        {/* Missing Info Contribution Prompt */}
        {!isEditing && isMissingInfo && showContribution && (
          <ContributionPrompt 
            type="missing_info"
            onClose={() => setShowContribution(false)}
            conversationId={conversationId}
            queryText={userQuery}
          />
        )}
        
        {/* High Value Signal Contribution Prompt */}
        {!isEditing && isHighValueSignal && showContribution && (
          <ContributionPrompt 
            type="high_value_signal"
            onClose={() => setShowContribution(false)}
            conversationId={conversationId}
            queryText={message.content}
          />
        )}
        
        {/* Actions for assistant messages */}
        {!isEditing && message.role === 'assistant' && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-dark-700">
            <button
              onClick={() => onFeedback('positive')}
              className={clsx(
                'btn-ghost p-1.5 text-xs',
                message.feedback === 'positive' && 'text-green-400 bg-green-500/10'
              )}
              title="有帮助"
            >
              <ThumbsUp size={14} />
            </button>
            <button
              onClick={() => onFeedback('negative')}
              className={clsx(
                'btn-ghost p-1.5 text-xs',
                message.feedback === 'negative' && 'text-red-400 bg-red-500/10'
              )}
              title="没帮助"
            >
              <ThumbsDown size={14} />
            </button>
            <button onClick={handleCopy} className="btn-ghost p-1.5 text-xs" title="复制">
              <Copy size={14} />
              {copied && <span className="ml-1">已复制</span>}
            </button>
            <button onClick={handleShare} className="btn-ghost p-1.5 text-xs" title="分享">
              <Share2 size={14} />
            </button>
          </div>
        )}
        
        {/* Actions for user messages */}
        {!isEditing && message.role === 'user' && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-dark-600 opacity-0 group-hover:opacity-100 transition-opacity">
            <button onClick={handleCopy} className="btn-ghost p-1.5 text-xs" title="复制">
              <Copy size={14} />
              {copied && <span className="ml-1">已复制</span>}
            </button>
            {canEdit && (
              <button onClick={handleStartEdit} className="btn-ghost p-1.5 text-xs" title="编辑">
                <Pencil size={14} />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// Upload status type
interface UploadStatus {
  type: 'uploading' | 'success' | 'error'
  fileName?: string
  message?: string
}

export default function Home() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const [input, setInput] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<UploadStatus | null>(null)
  const { messages, setMessages, addMessage, updateMessage, isSending, setSending } =
    useConversationStore()
  
  // Fetch messages when conversation changes
  const { data: messagesData, isLoading } = useQuery({
    queryKey: ['messages', conversationId],
    queryFn: () => conversationsApi.getMessages(conversationId!),
    enabled: !!conversationId,
  })
  
  // Create conversation mutation
  const createMutation = useMutation({
    mutationFn: conversationsApi.create,
    onSuccess: (conv) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      navigate(`/c/${conv.conversation_id}`)
    },
  })
  
  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: ({ convId, content }: { convId: string; content: string }) =>
      conversationsApi.sendMessage(convId, { content }),
    onSuccess: (message) => {
      addMessage(message)
      setSending(false)
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
    onError: () => {
      setSending(false)
    },
  })
  
  // Feedback mutation
  const feedbackMutation = useMutation({
    mutationFn: ({
      convId,
      messageId,
      feedback,
    }: {
      convId: string
      messageId: string
      feedback: 'positive' | 'negative'
    }) => conversationsApi.updateFeedback(convId, messageId, { feedback }),
    onSuccess: (_, variables) => {
      updateMessage(variables.messageId, { feedback: variables.feedback })
    },
  })
  
  // File upload handler
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    // Reset input so same file can be selected again
    e.target.value = ''
    
    // Check file size (50MB limit)
    const maxSize = 50 * 1024 * 1024
    if (file.size > maxSize) {
      setUploadStatus({
        type: 'error',
        message: '文件大小超过 50MB 限制'
      })
      return
    }
    
    setIsUploading(true)
    setUploadStatus({
      type: 'uploading',
      fileName: file.name
    })
    
    try {
      await contributeApi.uploadFile(file, {
        title: file.name,
        description: `通过对话界面上传`,
        ku_type_code: 'field.signal',
        conversation_id: conversationId,
        visibility: 'internal',
      })
      
      setUploadStatus({
        type: 'success',
        message: `文件 "${file.name}" 上传成功，待审核后入库`
      })
      
      // Auto clear success message after 5 seconds
      setTimeout(() => {
        setUploadStatus((prev) => prev?.type === 'success' ? null : prev)
      }, 5000)
    } catch (err) {
      setUploadStatus({
        type: 'error',
        message: `上传失败: ${err instanceof Error ? err.message : '未知错误'}`
      })
    } finally {
      setIsUploading(false)
    }
  }
  
  useEffect(() => {
    if (messagesData) {
      setMessages(messagesData.messages)
    }
  }, [messagesData, setMessages])
  
  useEffect(() => {
    // Scroll to bottom when messages change
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  const handleSend = async () => {
    if (!input.trim() || isSending) return
    
    const content = input.trim()
    setInput('')
    
    // If no conversation, create one first
    if (!conversationId) {
      setSending(true)
      const conv = await createMutation.mutateAsync({})
      
      // Add user message to UI immediately
      const userMessage: Message = {
        id: Date.now(),
        message_id: `temp-${Date.now()}`,
        role: 'user',
        content,
        sources: [],
        feedback: null,
        tokens_used: null,
        model_used: null,
        latency_ms: null,
        created_at: new Date().toISOString(),
      }
      addMessage(userMessage)
      
      // Send message
      sendMutation.mutate({ convId: conv.conversation_id, content })
    } else {
      setSending(true)
      
      // Add user message to UI immediately
      const userMessage: Message = {
        id: Date.now(),
        message_id: `temp-${Date.now()}`,
        role: 'user',
        content,
        sources: [],
        feedback: null,
        tokens_used: null,
        model_used: null,
        latency_ms: null,
        created_at: new Date().toISOString(),
      }
      addMessage(userMessage)
      
      // Send message
      sendMutation.mutate({ convId: conversationId, content })
    }
  }
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }
  
  const handleScenarioClick = (scenarioId: string) => {
    const prompts: Record<string, string> = {
      param: '/参数 ',
      case: '/案例 ',
      quote: '/报价 ',
      solution: '/方案 ',
      compare: '/对比 ',
      talk: '/话术 ',
    }
    setInput(prompts[scenarioId] || '')
  }
  
  // Handle edit message - truncate messages and resend
  const handleEditMessage = (messageId: string, newContent: string) => {
    if (!conversationId || isSending) return
    
    // Find the index of the message being edited
    const messageIndex = messages.findIndex(m => m.message_id === messageId)
    if (messageIndex === -1) return
    
    // Truncate messages to the edited message (remove it and everything after)
    const truncatedMessages = messages.slice(0, messageIndex)
    setMessages(truncatedMessages)
    
    // Send the new message
    setSending(true)
    
    // Add new user message to UI immediately
    const userMessage: Message = {
      id: Date.now(),
      message_id: `temp-${Date.now()}`,
      role: 'user',
      content: newContent,
      sources: [],
      feedback: null,
      tokens_used: null,
      model_used: null,
      latency_ms: null,
      created_at: new Date().toISOString(),
    }
    addMessage(userMessage)
    
    // Send message
    sendMutation.mutate({ convId: conversationId, content: newContent })
  }
  
  // Find the last user message index for edit capability
  const lastUserMessageIndex = messages.reduce((lastIdx, msg, idx) => {
    return msg.role === 'user' ? idx : lastIdx
  }, -1)
  
  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 size={32} className="animate-spin text-primary-500" />
          </div>
        ) : messages.length === 0 ? (
          /* Welcome Screen */
          <div className="flex flex-col items-center justify-center h-full p-8">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center mb-6">
              <span className="text-white text-3xl">🤖</span>
            </div>
            <h2 className="text-2xl font-bold mb-2">有什么可以帮您？</h2>
            <p className="text-dark-400 mb-8 text-center max-w-md">
              我可以帮您查询产品参数、检索案例、计算报价、生成方案...
            </p>
            
            {/* Scenario Cards */}
            <div className="grid grid-cols-3 gap-3 max-w-lg">
              {scenarios.map((scenario) => (
                <button
                  key={scenario.id}
                  onClick={() => handleScenarioClick(scenario.id)}
                  className="card p-4 hover:bg-dark-800/70 transition-all group"
                >
                  <scenario.icon
                    size={24}
                    className="mb-2 text-primary-400 group-hover:scale-110 transition-transform"
                  />
                  <span className="text-sm">{scenario.label}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message List */
          <div className="p-4 space-y-6 max-w-4xl mx-auto">
            {messages.map((message, index) => {
              // Find the previous user message for context
              const prevUserMessage = messages
                .slice(0, index)
                .reverse()
                .find(m => m.role === 'user')
              
              // Only the last user message can be edited (and not while sending)
              const canEdit = message.role === 'user' && 
                              index === lastUserMessageIndex && 
                              !isSending
              
              return (
                <MessageItem
                  key={message.message_id}
                  message={message}
                  conversationId={conversationId}
                  userQuery={prevUserMessage?.content}
                  canEdit={canEdit}
                  onEdit={handleEditMessage}
                  onFeedback={(feedback) => {
                    if (conversationId) {
                      feedbackMutation.mutate({
                        convId: conversationId,
                        messageId: message.message_id,
                        feedback,
                      })
                    }
                  }}
                />
              )
            })}
            
            {/* Typing Indicator */}
            {isSending && (
              <div className="flex gap-3 animate-fade-in">
                <div className="w-8 h-8 rounded-full bg-dark-700 flex items-center justify-center">
                  🤖
                </div>
                <div className="message-assistant p-4">
                  <div className="typing-indicator flex gap-1">
                    <span className="w-2 h-2 bg-dark-400 rounded-full"></span>
                    <span className="w-2 h-2 bg-dark-400 rounded-full"></span>
                    <span className="w-2 h-2 bg-dark-400 rounded-full"></span>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>
      
      {/* Input Area */}
      <div className="border-t border-dark-800 p-4 bg-dark-900/50">
        <div className="max-w-4xl mx-auto">
          {/* Upload Status Bar */}
          {uploadStatus && (
            <div className={clsx(
              'mb-3 p-3 rounded-lg flex items-center gap-3',
              uploadStatus.type === 'uploading' && 'bg-dark-800',
              uploadStatus.type === 'success' && 'bg-green-500/10 border border-green-500/30',
              uploadStatus.type === 'error' && 'bg-red-500/10 border border-red-500/30'
            )}>
              {uploadStatus.type === 'uploading' && (
                <>
                  <Loader2 size={16} className="animate-spin text-primary-400" />
                  <span className="text-sm">上传中: {uploadStatus.fileName}</span>
                </>
              )}
              {uploadStatus.type === 'success' && (
                <>
                  <Check size={16} className="text-green-400" />
                  <span className="text-sm text-green-400">{uploadStatus.message}</span>
                </>
              )}
              {uploadStatus.type === 'error' && (
                <>
                  <X size={16} className="text-red-400" />
                  <span className="text-sm text-red-400">{uploadStatus.message}</span>
                </>
              )}
              <button
                onClick={() => setUploadStatus(null)}
                className="ml-auto text-dark-400 hover:text-dark-200"
              >
                <X size={14} />
              </button>
            </div>
          )}
          
          <div className="relative flex items-end gap-2">
            {/* File Upload Button */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md,.csv"
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="btn-ghost p-3 shrink-0"
              title="上传文件"
            >
              {isUploading ? (
                <Loader2 size={18} className="animate-spin text-primary-400" />
              ) : (
                <Upload size={18} className="text-dark-400 hover:text-primary-400" />
              )}
            </button>
            
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入问题或使用快捷命令 (/案例, /报价, /方案, /对比, /话术)"
                rows={1}
                className="input pr-12 py-3 resize-none min-h-[48px] max-h-[200px] w-full"
                style={{ height: 'auto' }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = 'auto'
                  target.style.height = Math.min(target.scrollHeight, 200) + 'px'
                }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isSending}
                className="absolute right-2 bottom-2 btn-primary p-2"
              >
                {isSending ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <Send size={18} />
                )}
              </button>
            </div>
          </div>
          <p className="text-xs text-dark-500 mt-2 text-center">
            按 Enter 发送，Shift+Enter 换行 | 点击 <Upload size={12} className="inline" /> 上传文件
          </p>
        </div>
      </div>
    </div>
  )
}

