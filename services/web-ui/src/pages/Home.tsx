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
  Paperclip,
} from 'lucide-react'
import { useNavigate as useRouterNavigate } from 'react-router-dom'
import { conversationsApi } from '../api/conversations'
import { contributeApi } from '../api/contribute'
import { interactionApi, InteractionStep } from '../api/interaction'
import { useConversationStore, Message, InteractionData } from '../store/conversationStore'
import MarkdownRenderer from '../components/MarkdownRenderer'
import InteractiveCard from '../components/chat/InteractiveCard'
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
  onInteractionAnswer?: (sessionId: string, stepId: string, answer: string | string[]) => void
  onInteractionCancel?: (sessionId: string) => void
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

function MessageItem({ message, onFeedback, onEdit, onInteractionAnswer, onInteractionCancel, conversationId, userQuery, canEdit }: MessageItemProps) {
  const [copied, setCopied] = useState(false)
  const [shared, setShared] = useState(false)
  const [showContribution, setShowContribution] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState(message.content)
  const [shareError, setShareError] = useState<string | null>(null)
  const [isInteractionLoading, setIsInteractionLoading] = useState(false)
  
  // Reset loading when interaction data changes (new question means previous answer was processed)
  // Using JSON stringify to detect any change in the interaction object
  const interactionKey = message.interaction ? JSON.stringify({
    step: message.interaction.currentStep,
    questionId: message.interaction.question?.id
  }) : null
  
  useEffect(() => {
    // Always reset loading when interaction state changes
    setIsInteractionLoading(false)
  }, [interactionKey])
  
  // Helper function to copy text to clipboard (works on HTTP and HTTPS)
  const copyToClipboard = async (text: string): Promise<boolean> => {
    // Try modern clipboard API first (requires HTTPS)
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text)
        return true
      } catch (err) {
        console.warn('Clipboard API failed, trying fallback:', err)
      }
    }
    
    // Fallback for HTTP or older browsers
    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.style.position = 'fixed'
    textArea.style.left = '-9999px'
    textArea.style.top = '-9999px'
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    
    try {
      const successful = document.execCommand('copy')
      document.body.removeChild(textArea)
      return successful
    } catch (err) {
      console.error('Fallback copy failed:', err)
      document.body.removeChild(textArea)
      return false
    }
  }
  
  const handleCopy = async () => {
    const success = await copyToClipboard(message.content)
    if (success) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }
  
  const handleShare = async () => {
    if (!conversationId) {
      setShareError('请先发送消息后再分享')
      setTimeout(() => setShareError(null), 3000)
      return
    }
    
    try {
      const result = await conversationsApi.createShare(conversationId)
      // Build full URL from relative path
      const baseUrl = window.location.origin
      const fullShareUrl = result.share_url.startsWith('http') 
        ? result.share_url 
        : `${baseUrl}${result.share_url}`
      
      const success = await copyToClipboard(fullShareUrl)
      if (success) {
        setShared(true)
        setTimeout(() => setShared(false), 2000)
      } else {
        setShareError('复制链接失败')
        setTimeout(() => setShareError(null), 3000)
      }
    } catch (error) {
      console.error('Share failed:', error)
      setShareError('分享失败，请稍后重试')
      setTimeout(() => setShareError(null), 3000)
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
        
        {/* Interactive Question Card */}
        {!isEditing && message.interaction && onInteractionAnswer && onInteractionCancel && (
          <div className="mt-4">
            <InteractiveCard
              flowName={message.interaction.flowName}
              question={message.interaction.question}
              progress={{
                answered: message.interaction.currentStep,
                total: message.interaction.totalSteps
              }}
              onAnswer={(stepId, answer) => {
                setIsInteractionLoading(true)
                onInteractionAnswer(message.interaction!.sessionId, stepId, answer)
              }}
              onCancel={() => onInteractionCancel(message.interaction!.sessionId)}
              isLoading={isInteractionLoading}
            />
          </div>
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
            <button onClick={handleShare} className="btn-ghost p-1.5 text-xs" title="分享对话">
              <Share2 size={14} />
              {shared && <span className="ml-1">已分享</span>}
            </button>
            {shareError && (
              <span className="text-xs text-red-400 ml-2">{shareError}</span>
            )}
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

// Attached file type for message context
interface AttachedFile {
  file: File
  preview?: string  // Data URL for image preview
  isImage: boolean
  // Classification suggestion
  classification?: {
    ku_type_code: string
    ku_type_name: string
    product_id?: string
    tags: string[]
    confidence: number
    reason: string
  }
  isClassifying?: boolean
}

// Supported file types
const SUPPORTED_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
const SUPPORTED_DOC_TYPES = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'text/plain',
  'text/markdown',
]

const FILE_ACCEPT = '.jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md'

export default function Home() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const [input, setInput] = useState('')
  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<UploadStatus | null>(null)
  const [isDragActive, setIsDragActive] = useState(false)
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
      // 处理新版动态交互格式（API返回snake_case，需要转换为camelCase）
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const rawInteraction = message.interaction as any
      if (rawInteraction && rawInteraction.question) {
        // 转换为前端期望的 InteractionData 格式
        const interactionData: InteractionData = {
          sessionId: rawInteraction.session_id || rawInteraction.sessionId,
          flowId: 'dynamic',  // 动态模式不绑定静态流程
          flowName: '智能问答',
          currentStep: rawInteraction.progress?.answered ?? 0,
          totalSteps: rawInteraction.progress?.total ?? 1,
          question: {
            id: rawInteraction.question.field_id || rawInteraction.question.id,
            question: rawInteraction.question.question,
            type: (rawInteraction.question.question_type || rawInteraction.question.type || 'single') as 'single' | 'multiple' | 'input',
            options: rawInteraction.question.options?.map((opt: { id: string; label: string }) => ({
              id: opt.id,
              label: opt.label
            })),
            placeholder: rawInteraction.question.placeholder,
          },
          collectedAnswers: {},
        }
        
        // 添加带交互数据的消息
        addMessage({
          ...message,
          interaction: interactionData,
        })
      } else {
        addMessage(message)
      }
      
      setSending(false)
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      
      // 检查是否有 LLM 智能触发的交互流程（兼容旧版）
      if (message.interaction_trigger && conversationId) {
        const trigger = message.interaction_trigger
        console.log(`LLM triggered interaction flow: ${trigger.flow_id} (conf=${trigger.confidence})`)
        
        // 自动启动交互流程
        void startInteractionFlow(trigger.flow_id)
      }
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
  
  // NOTE: Removed flowsData query - frontend no longer triggers static flows.
  // The backend unified intent router handles all routing decisions.
  
  // Active interaction session state
  const [activeInteraction, setActiveInteraction] = useState<{
    sessionId: string
    flowId: string
    flowName: string
    currentStep: number
    totalSteps: number
    question: InteractionStep | null
    collectedAnswers: Record<string, string | string[]>
  } | null>(null)
  
  // Start interaction flow (can be triggered by user action or automatic detection)
  const startInteractionFlow = async (flowId: string) => {
    if (!conversationId) return
    
    try {
      const result = await interactionApi.startSession(conversationId, flowId)
      
      if (result.current_question) {
        setActiveInteraction({
          sessionId: result.session.session_id,
          flowId: result.flow.flow_id,
          flowName: result.flow.name,
          currentStep: 0,
          totalSteps: result.flow.total_steps,
          question: result.current_question,
          collectedAnswers: {},
        })
        
        // Add an assistant message with the interaction
        const interactionMessage: Message = {
          id: Date.now(),
          message_id: `interaction-${result.session.session_id}`,
          role: 'assistant',
          content: `为了更好地帮助您，请回答以下问题：`,
          sources: [],
          feedback: null,
          tokens_used: null,
          model_used: null,
          latency_ms: null,
          created_at: new Date().toISOString(),
          interaction: {
            sessionId: result.session.session_id,
            flowId: result.flow.flow_id,
            flowName: result.flow.name,
            currentStep: 0,
            totalSteps: result.flow.total_steps,
            question: result.current_question,
            collectedAnswers: {},
          },
        }
        addMessage(interactionMessage)
      }
    } catch (error) {
      console.error('Failed to start interaction:', error)
    }
  }
  
  // Handle interaction answer - supports both static flows and dynamic mode
  const handleInteractionAnswer = async (sessionId: string, stepId: string, answer: string | string[]) => {
    // Check if this is a dynamic session (sessionId starts with 'dyn_')
    const isDynamic = sessionId.startsWith('dyn_')
    
    if (isDynamic && conversationId) {
      // Dynamic mode - send answer as regular message
      // The backend will handle it through the active session detection
      const answerText = Array.isArray(answer) ? answer.join(', ') : answer
      setSending(true)
      
      // Update the message to remove interaction UI temporarily
      const messageId = messages.find(m => m.interaction?.sessionId === sessionId)?.message_id
      if (messageId) {
        updateMessage(messageId, { interaction: undefined })
      }
      
      // Send the answer as a regular message
      sendMutation.mutate({
        convId: conversationId,
        content: answerText,
      })
      return
    }
    
    // Static flow mode - use the interaction API
    try {
      const result = await interactionApi.submitAnswer(sessionId, stepId, answer)
      
      if (result.completed) {
        // Interaction completed - remove from active and update the message
        setActiveInteraction(null)
        
        // Update the message to remove interaction UI
        const messageId = `interaction-${sessionId}`
        updateMessage(messageId, { interaction: undefined })
        
        // Construct a summary of answers - use labeled_answers if available (human-readable)
        const answersToDisplay = result.labeled_answers || result.collected_answers || {}
        const answersText = Object.entries(answersToDisplay)
          .map(([key, val]) => `${key}: ${Array.isArray(val) ? val.join(', ') : val}`)
          .join('\n')
        
        // Add user message with collected answers
        const userMessage: Message = {
          id: Date.now(),
          message_id: `answers-${sessionId}`,
          role: 'user',
          content: `[已收集信息]\n${answersText}`,
          sources: [],
          feedback: null,
          tokens_used: null,
          model_used: null,
          latency_ms: null,
          created_at: new Date().toISOString(),
        }
        addMessage(userMessage)
        
        // Trigger follow-up based on on_complete action
        if (conversationId && result.on_complete) {
          setSending(true)
          // Send the collected answers to get AI response
          sendMutation.mutate({
            convId: conversationId,
            content: `基于以下信息进行${result.on_complete === 'calculate' ? '计算' : result.on_complete === 'search' ? '检索' : '生成回答'}:\n${answersText}`,
          })
        }
      } else if (result.current_question) {
        // Update to next question
        const messageId = `interaction-${sessionId}`
        updateMessage(messageId, {
          interaction: {
            sessionId,
            flowId: activeInteraction?.flowId || '',
            flowName: activeInteraction?.flowName || '',
            currentStep: result.progress?.answered || 0,
            totalSteps: result.progress?.total || 1,
            question: result.current_question,
            collectedAnswers: result.session.collected_answers,
          },
        })
        
        setActiveInteraction((prev) =>
          prev
            ? {
                ...prev,
                currentStep: result.progress?.answered || 0,
                question: result.current_question!,
                collectedAnswers: result.session.collected_answers,
              }
            : null
        )
      }
    } catch (error) {
      console.error('Failed to submit answer:', error)
    }
  }
  
  // Handle interaction cancel
  const handleInteractionCancel = async (sessionId: string) => {
    try {
      await interactionApi.cancelSession(sessionId)
      setActiveInteraction(null)
      
      // Remove the interaction message
      const messageId = `interaction-${sessionId}`
      updateMessage(messageId, { interaction: undefined, content: '交互已取消' })
    } catch (error) {
      console.error('Failed to cancel interaction:', error)
    }
  }
  
  // File attachment handler - attach file as message context
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    // Reset input so same file can be selected again
    e.target.value = ''
    
    void processFile(file)
  }
  
  // Remove attached file
  const handleRemoveAttachment = () => {
    setAttachedFile(null)
  }
  
  // Get file icon based on extension
  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase()
    if (['pdf'].includes(ext || '')) return '📄'
    if (['doc', 'docx'].includes(ext || '')) return '📝'
    if (['xls', 'xlsx'].includes(ext || '')) return '📊'
    if (['ppt', 'pptx'].includes(ext || '')) return '📽️'
    if (['txt', 'md'].includes(ext || '')) return '📃'
    return '📎'
  }
  
  // Format file size
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }
  
  // Process file (shared between file input and drag drop)
  const processFile = async (file: File) => {
    // Check file type
    const isImage = SUPPORTED_IMAGE_TYPES.includes(file.type)
    const isDoc = SUPPORTED_DOC_TYPES.includes(file.type) || 
                  file.name.endsWith('.md') || 
                  file.name.endsWith('.txt')
    
    if (!isImage && !isDoc) {
      setUploadStatus({
        type: 'error',
        message: '不支持的文件类型，请上传图片或文档'
      })
      setTimeout(() => setUploadStatus(null), 4000)
      return
    }
    
    // Check file size (50MB limit)
    const maxSize = 50 * 1024 * 1024
    if (file.size > maxSize) {
      setUploadStatus({
        type: 'error',
        message: '文件大小超过 50MB 限制'
      })
      setTimeout(() => setUploadStatus(null), 4000)
      return
    }
    
    // Create preview for images
    if (isImage) {
      const reader = new FileReader()
      reader.onload = (event) => {
        setAttachedFile({
          file,
          preview: event.target?.result as string,
          isImage: true,
        })
      }
      reader.readAsDataURL(file)
    } else {
      // For documents, set file and start classification
      setAttachedFile({
        file,
        isImage: false,
        isClassifying: true,
      })
      
      // Try to extract text content for classification
      let textContent = ''
      try {
        // For text/markdown files, read content directly
        if (file.type === 'text/plain' || file.name.endsWith('.md') || file.name.endsWith('.txt')) {
          textContent = await file.text()
          textContent = textContent.slice(0, 2000) // First 2000 chars
        } else {
          // For other docs, use filename as hint
          textContent = `文件名: ${file.name}\n文件类型: ${file.type}\n文件大小: ${formatFileSize(file.size)}`
        }
        
        // Call classification API
        const classification = await contributeApi.classify({
          filename: file.name,
          content: textContent,
          mime_type: file.type,
        })
        
        setAttachedFile(prev => prev ? {
          ...prev,
          classification,
          isClassifying: false,
        } : null)
      } catch (error) {
        console.error('Classification failed:', error)
        setAttachedFile(prev => prev ? {
          ...prev,
          isClassifying: false,
        } : null)
      }
    }
  }
  
  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!isDragActive) setIsDragActive(true)
  }
  
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)
  }
  
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)
    
    const file = e.dataTransfer.files?.[0]
    if (file) {
      void processFile(file)
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
    if ((!input.trim() && !attachedFile) || isSending) return
    
    const content = input.trim()
    const fileToUpload = attachedFile
    
    // NOTE: Static interaction flow trigger logic has been removed.
    // The backend unified intent router now handles all routing decisions,
    // including dynamic question generation based on context sufficiency.
    // This ensures queries like "工控安全案例" are searched directly
    // instead of triggering a generic "案例检索流程".
    
    // Clear input and attachment
    setInput('')
    setAttachedFile(null)
    
    // Build display content for user message
    let displayContent = content
    if (fileToUpload) {
      const fileInfo = `📎 ${fileToUpload.file.name}`
      displayContent = content ? `${fileInfo}\n\n${content}` : fileInfo
    }
    
    // If no conversation, create one first
    if (!conversationId) {
      setSending(true)
      const conv = await createMutation.mutateAsync({})
      
      // Add user message to UI immediately
      const userMessage: Message = {
        id: Date.now(),
        message_id: `temp-${Date.now()}`,
        role: 'user',
        content: displayContent,
        sources: [],
        feedback: null,
        tokens_used: null,
        model_used: null,
        latency_ms: null,
        created_at: new Date().toISOString(),
      }
      addMessage(userMessage)
      
      // Upload file first if attached, then send message
      if (fileToUpload) {
        try {
          setIsUploading(true)
          // Use classification result if available, otherwise default to field.signal
          const kuType = fileToUpload.classification?.ku_type_code || 'field.signal'
          const tags = fileToUpload.classification?.tags || []
          await contributeApi.uploadFile(fileToUpload.file, {
            title: fileToUpload.file.name,
            description: content || `通过对话界面上传`,
            ku_type_code: kuType,
            product_id: fileToUpload.classification?.product_id,
            tags: tags,
            conversation_id: conv.conversation_id,
            visibility: 'internal',
          })
          setIsUploading(false)
        } catch (err) {
          setIsUploading(false)
          console.error('File upload failed:', err)
        }
      }
      
      // Send message
      sendMutation.mutate({ convId: conv.conversation_id, content: displayContent })
    } else {
      setSending(true)
      
      // Add user message to UI immediately
      const userMessage: Message = {
        id: Date.now(),
        message_id: `temp-${Date.now()}`,
        role: 'user',
        content: displayContent,
        sources: [],
        feedback: null,
        tokens_used: null,
        model_used: null,
        latency_ms: null,
        created_at: new Date().toISOString(),
      }
      addMessage(userMessage)
      
      // Upload file first if attached, then send message
      if (fileToUpload) {
        try {
          setIsUploading(true)
          // Use classification result if available, otherwise default to field.signal
          const kuType = fileToUpload.classification?.ku_type_code || 'field.signal'
          const tags = fileToUpload.classification?.tags || []
          await contributeApi.uploadFile(fileToUpload.file, {
            title: fileToUpload.file.name,
            description: content || `通过对话界面上传`,
            ku_type_code: kuType,
            product_id: fileToUpload.classification?.product_id,
            tags: tags,
            conversation_id: conversationId,
            visibility: 'internal',
          })
          setIsUploading(false)
        } catch (err) {
          setIsUploading(false)
          console.error('File upload failed:', err)
        }
      }
      
      // Send message
      sendMutation.mutate({ convId: conversationId, content: displayContent })
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
                  onInteractionAnswer={handleInteractionAnswer}
                  onInteractionCancel={handleInteractionCancel}
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
          {/* Error Status Bar */}
          {uploadStatus?.type === 'error' && (
            <div className="mb-3 p-3 rounded-lg flex items-center gap-3 bg-red-500/10 border border-red-500/30">
              <X size={16} className="text-red-400" />
              <span className="text-sm text-red-400">{uploadStatus.message}</span>
              <button
                onClick={() => setUploadStatus(null)}
                className="ml-auto text-dark-400 hover:text-dark-200"
              >
                <X size={14} />
              </button>
            </div>
          )}
          
          {/* Attached File Preview - Above Input */}
          {attachedFile && (
            <div className="mb-3 p-3 bg-dark-800/80 rounded-lg border border-dark-700 animate-fade-in">
              <div className="flex items-center gap-3">
                {/* Preview */}
                {attachedFile.isImage && attachedFile.preview ? (
                  <div className="w-16 h-16 rounded-lg overflow-hidden bg-dark-700 shrink-0">
                    <img 
                      src={attachedFile.preview} 
                      alt="Preview" 
                      className="w-full h-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="w-12 h-12 rounded-lg bg-dark-700 flex items-center justify-center shrink-0">
                    <span className="text-2xl">{getFileIcon(attachedFile.file.name)}</span>
                  </div>
                )}
                
                {/* File Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-dark-100 truncate">
                    {attachedFile.file.name}
                  </p>
                  <p className="text-xs text-dark-400">
                    {formatFileSize(attachedFile.file.size)}
                    {attachedFile.isImage && ' • 图片'}
                  </p>
                </div>
                
                {/* Remove Button */}
                <button
                  onClick={handleRemoveAttachment}
                  className="p-1.5 rounded-full hover:bg-dark-600 text-dark-400 hover:text-dark-200 transition-colors"
                  title="移除附件"
                >
                  <X size={16} />
                </button>
              </div>
              
              {/* Classification Suggestion */}
              {attachedFile.isClassifying && (
                <div className="mt-3 pt-3 border-t border-dark-700 flex items-center gap-2 text-sm text-dark-400">
                  <Loader2 size={14} className="animate-spin" />
                  <span>正在智能分类...</span>
                </div>
              )}
              
              {attachedFile.classification && !attachedFile.isClassifying && (
                <div className="mt-3 pt-3 border-t border-dark-700">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs text-dark-400">AI 识别:</span>
                    <span className={clsx(
                      "px-2 py-0.5 rounded text-xs font-medium",
                      attachedFile.classification.confidence >= 0.7 
                        ? "bg-green-500/20 text-green-400"
                        : attachedFile.classification.confidence >= 0.5
                        ? "bg-yellow-500/20 text-yellow-400"
                        : "bg-dark-600 text-dark-300"
                    )}>
                      {attachedFile.classification.ku_type_name}
                    </span>
                    {attachedFile.classification.product_id && (
                      <span className="px-2 py-0.5 rounded text-xs bg-primary-500/20 text-primary-400">
                        {attachedFile.classification.product_id}
                      </span>
                    )}
                    <span className="text-xs text-dark-500 ml-auto">
                      置信度 {Math.round(attachedFile.classification.confidence * 100)}%
                    </span>
                  </div>
                  {attachedFile.classification.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {attachedFile.classification.tags.slice(0, 5).map((tag, i) => (
                        <span key={i} className="px-1.5 py-0.5 rounded text-xs bg-dark-700 text-dark-300">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="text-xs text-dark-500 mt-1 italic">
                    {attachedFile.classification.reason}
                  </p>
                </div>
              )}
            </div>
          )}
          
          {/* Input Container */}
          <div 
            className={clsx(
              "relative flex items-end gap-0 bg-dark-800 rounded-xl border transition-colors",
              isDragActive 
                ? "border-primary-500 bg-primary-500/5 ring-2 ring-primary-500/20" 
                : "border-dark-700 focus-within:border-primary-500/50"
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {/* Drag overlay */}
            {isDragActive && (
              <div className="absolute inset-0 flex items-center justify-center bg-primary-500/10 rounded-xl pointer-events-none z-10">
                <div className="flex items-center gap-2 text-primary-400 font-medium">
                  <Paperclip size={20} />
                  <span>放开以添加附件</span>
                </div>
              </div>
            )}
            {/* File Attachment Button */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept={FILE_ACCEPT}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading || isSending}
              className={clsx(
                'p-3 shrink-0 transition-colors rounded-l-xl',
                'hover:bg-dark-700/50 active:bg-dark-700',
                attachedFile ? 'text-primary-400' : 'text-dark-400 hover:text-dark-200'
              )}
              title="添加附件"
            >
              {isUploading ? (
                <Loader2 size={20} className="animate-spin text-primary-400" />
              ) : (
                <Paperclip size={20} />
              )}
            </button>
            
            {/* Divider */}
            <div className="w-px h-6 bg-dark-700 self-center" />
            
            {/* Text Input */}
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={attachedFile ? "描述你想了解的内容..." : "输入问题或使用快捷命令 (/案例, /报价, /方案...)"}
                rows={1}
                className="w-full bg-transparent text-dark-100 placeholder-dark-500 py-3 px-3 resize-none min-h-[48px] max-h-[200px] focus:outline-none"
                style={{ height: 'auto' }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = 'auto'
                  target.style.height = Math.min(target.scrollHeight, 200) + 'px'
                }}
              />
            </div>
            
            {/* Send Button */}
            <button
              onClick={handleSend}
              disabled={(!input.trim() && !attachedFile) || isSending}
              className={clsx(
                'p-3 shrink-0 transition-all rounded-r-xl',
                (!input.trim() && !attachedFile) || isSending
                  ? 'text-dark-500 cursor-not-allowed'
                  : 'text-primary-400 hover:bg-primary-500/10 active:bg-primary-500/20'
              )}
              title="发送消息"
            >
              {isSending ? (
                <Loader2 size={20} className="animate-spin" />
              ) : (
                <Send size={20} />
              )}
            </button>
          </div>
          
          {/* Help Text */}
          <p className="text-xs text-dark-500 mt-2 text-center">
            Enter 发送 · Shift+Enter 换行 · 点击 <Paperclip size={10} className="inline" /> 添加附件
          </p>
        </div>
      </div>
    </div>
  )
}

