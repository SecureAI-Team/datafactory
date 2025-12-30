import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2, ExternalLink, Copy, Check } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { conversationsApi } from '../api/conversations'
import { useState } from 'react'
import clsx from 'clsx'

export default function SharedChat() {
  const { token } = useParams<{ token: string }>()
  const [copiedId, setCopiedId] = useState<string | null>(null)
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['shared-conversation', token],
    queryFn: () => conversationsApi.getShared(token!),
    enabled: !!token,
  })
  
  const handleCopy = (content: string, id: string) => {
    if (!data?.allow_copy) return
    navigator.clipboard.writeText(content)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }
  
  if (isLoading) {
    return (
      <div className="min-h-screen bg-dark-950 flex items-center justify-center">
        <Loader2 size={48} className="animate-spin text-primary-500" />
      </div>
    )
  }
  
  if (error || !data) {
    return (
      <div className="min-h-screen bg-dark-950 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4">😔</div>
          <h1 className="text-2xl font-bold mb-2">分享链接无效或已过期</h1>
          <p className="text-dark-400">请联系分享者获取新的链接</p>
        </div>
      </div>
    )
  }
  
  return (
    <div className="min-h-screen bg-dark-950">
      {/* Header */}
      <header className="bg-dark-900 border-b border-dark-800 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <span className="text-white font-bold text-sm">AI</span>
            </div>
            <div>
              <h1 className="font-semibold">{data.conversation.title || '对话分享'}</h1>
              <p className="text-xs text-dark-400">分享于 {data.shared_at}</p>
            </div>
          </div>
          
          <a
            href="/"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary text-sm"
          >
            <ExternalLink size={16} />
            打开完整版
          </a>
        </div>
      </header>
      
      {/* Messages */}
      <main className="max-w-4xl mx-auto p-4">
        <div className="space-y-6">
          {data.messages.map((message) => (
            <div
              key={message.message_id}
              className={clsx(
                'flex gap-3',
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
                {message.role === 'user' ? '👤' : '🤖'}
              </div>
              
              {/* Content */}
              <div
                className={clsx(
                  'max-w-[75%] p-4 group',
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
                
                {/* Copy button */}
                {data.allow_copy && (
                  <button
                    onClick={() => handleCopy(message.content, message.message_id)}
                    className="opacity-0 group-hover:opacity-100 absolute top-2 right-2 btn-ghost p-1.5 text-xs transition-opacity"
                  >
                    {copiedId === message.message_id ? (
                      <Check size={14} className="text-green-400" />
                    ) : (
                      <Copy size={14} />
                    )}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
        
        {/* Footer */}
        <div className="mt-12 text-center text-sm text-dark-500">
          <p>此对话由 AI 数据工厂 生成</p>
          {!data.allow_copy && (
            <p className="mt-1 text-dark-400">🔒 分享者禁止了复制功能</p>
          )}
        </div>
      </main>
    </div>
  )
}

