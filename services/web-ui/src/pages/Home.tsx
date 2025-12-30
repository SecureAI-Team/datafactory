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
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { conversationsApi } from '../api/conversations'
import { useConversationStore, Message } from '../store/conversationStore'
import clsx from 'clsx'

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
}

function MessageItem({ message, onFeedback }: MessageItemProps) {
  const [copied, setCopied] = useState(false)
  
  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  
  return (
    <div
      className={clsx(
        'flex gap-3 animate-fade-in',
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
        <div className="prose-chat">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
        
        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
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
        
        {/* Actions for assistant messages */}
        {message.role === 'assistant' && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-dark-700">
            <button
              onClick={() => onFeedback('positive')}
              className={clsx(
                'btn-ghost p-1.5 text-xs',
                message.feedback === 'positive' && 'text-green-400 bg-green-500/10'
              )}
            >
              <ThumbsUp size={14} />
            </button>
            <button
              onClick={() => onFeedback('negative')}
              className={clsx(
                'btn-ghost p-1.5 text-xs',
                message.feedback === 'negative' && 'text-red-400 bg-red-500/10'
              )}
            >
              <ThumbsDown size={14} />
            </button>
            <button onClick={handleCopy} className="btn-ghost p-1.5 text-xs">
              <Copy size={14} />
              {copied && <span className="ml-1">已复制</span>}
            </button>
            <button className="btn-ghost p-1.5 text-xs">
              <Share2 size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Home() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const [input, setInput] = useState('')
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
            {messages.map((message) => (
              <MessageItem
                key={message.message_id}
                message={message}
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
            ))}
            
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
          <div className="relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入问题或使用快捷命令 (/案例, /报价, /方案, /对比, /话术)"
              rows={1}
              className="input pr-12 py-3 resize-none min-h-[48px] max-h-[200px]"
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
          <p className="text-xs text-dark-500 mt-2 text-center">
            按 Enter 发送，Shift+Enter 换行
          </p>
        </div>
      </div>
    </div>
  )
}

