import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Search,
  MessageSquare,
  Pin,
  Archive,
  MoreHorizontal,
  Trash2,
  Edit3,
  Settings,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { conversationsApi } from '../../api/conversations'
import { useConversationStore, Conversation } from '../../store/conversationStore'
import clsx from 'clsx'

interface ConversationGroupProps {
  title: string
  icon?: React.ReactNode
  conversations: Conversation[]
  defaultOpen?: boolean
}

function ConversationGroup({ title, conversations, defaultOpen = true }: ConversationGroupProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const navigate = useNavigate()
  const { conversationId } = useParams()
  const queryClient = useQueryClient()
  const [contextMenu, setContextMenu] = useState<{ id: string; x: number; y: number } | null>(null)
  
  const deleteMutation = useMutation({
    mutationFn: conversationsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
  })
  
  const pinMutation = useMutation({
    mutationFn: ({ id, pinned }: { id: string; pinned: boolean }) =>
      conversationsApi.pin(id, pinned),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
  })
  
  const archiveMutation = useMutation({
    mutationFn: conversationsApi.archive,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
  })
  
  if (conversations.length === 0) return null
  
  const handleContextMenu = (e: React.MouseEvent, id: string) => {
    e.preventDefault()
    setContextMenu({ id, x: e.clientX, y: e.clientY })
  }
  
  const closeContextMenu = () => setContextMenu(null)
  
  return (
    <div className="mb-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 w-full text-xs font-medium text-dark-400 hover:text-dark-300 uppercase tracking-wider"
      >
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {title}
        <span className="ml-auto text-dark-500">{conversations.length}</span>
      </button>
      
      {isOpen && (
        <div className="space-y-0.5 mt-1">
          {conversations.map((conv) => (
            <div
              key={conv.conversation_id}
              onClick={() => navigate(`/c/${conv.conversation_id}`)}
              onContextMenu={(e) => handleContextMenu(e, conv.conversation_id)}
              className={clsx(
                'group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer',
                'hover:bg-dark-800/50 transition-all duration-150',
                conversationId === conv.conversation_id && 'bg-primary-500/10 text-primary-400'
              )}
            >
              <MessageSquare size={16} className="shrink-0 text-dark-400" />
              <span className="flex-1 truncate text-sm">
                {conv.title || '新对话'}
              </span>
              {conv.is_pinned && <Pin size={12} className="text-primary-400" />}
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleContextMenu(e, conv.conversation_id)
                }}
                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-dark-700 rounded"
              >
                <MoreHorizontal size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
      
      {/* Context Menu */}
      {contextMenu && (
        <>
          <div className="fixed inset-0 z-40" onClick={closeContextMenu} />
          <div
            className="fixed z-50 bg-dark-800 border border-dark-700 rounded-lg shadow-xl py-1 min-w-[160px]"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            <button
              onClick={() => {
                // TODO: Implement rename
                closeContextMenu()
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-dark-700"
            >
              <Edit3 size={14} /> 重命名
            </button>
            <button
              onClick={() => {
                const conv = conversations.find((c) => c.conversation_id === contextMenu.id)
                if (conv) {
                  pinMutation.mutate({ id: conv.conversation_id, pinned: !conv.is_pinned })
                }
                closeContextMenu()
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-dark-700"
            >
              <Pin size={14} /> {conversations.find((c) => c.conversation_id === contextMenu.id)?.is_pinned ? '取消置顶' : '置顶'}
            </button>
            <button
              onClick={() => {
                archiveMutation.mutate(contextMenu.id)
                closeContextMenu()
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-dark-700"
            >
              <Archive size={14} /> 归档
            </button>
            <div className="h-px bg-dark-700 my-1" />
            <button
              onClick={() => {
                deleteMutation.mutate(contextMenu.id)
                closeContextMenu()
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-400 hover:bg-dark-700"
            >
              <Trash2 size={14} /> 删除
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default function Sidebar() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const { setConversations, setCurrentConversation } = useConversationStore()
  
  // Fetch conversations
  const { data: conversations } = useQuery({
    queryKey: ['conversations'],
    queryFn: conversationsApi.list,
    refetchInterval: 30000, // Refresh every 30s
  })
  
  // Create new conversation
  const createMutation = useMutation({
    mutationFn: conversationsApi.create,
    onSuccess: (newConv) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      navigate(`/c/${newConv.conversation_id}`)
    },
  })
  
  // Search conversations
  const { data: searchResults } = useQuery({
    queryKey: ['conversations', 'search', searchQuery],
    queryFn: () => conversationsApi.search(searchQuery),
    enabled: searchQuery.length > 0,
  })
  
  useEffect(() => {
    if (conversations) {
      setConversations(conversations)
    }
  }, [conversations, setConversations])
  
  const handleNewChat = () => {
    createMutation.mutate({})
  }
  
  return (
    <aside className="w-72 bg-dark-900 border-r border-dark-800 flex flex-col">
      {/* Logo & New Chat */}
      <div className="p-4 border-b border-dark-800">
        <button
          onClick={handleNewChat}
          disabled={createMutation.isPending}
          className="w-full btn-primary"
        >
          <Plus size={18} />
          新建对话
        </button>
      </div>
      
      {/* Search */}
      <div className="p-3">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-400" />
          <input
            type="text"
            placeholder="搜索历史..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input pl-9 py-2 text-sm"
          />
        </div>
      </div>
      
      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-2">
        {searchQuery ? (
          // Search Results
          <div>
            <div className="px-3 py-2 text-xs text-dark-400 uppercase">搜索结果</div>
            {searchResults?.results.map((conv) => (
              <div
                key={conv.conversation_id}
                onClick={() => {
                  navigate(`/c/${conv.conversation_id}`)
                  setSearchQuery('')
                }}
                className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer hover:bg-dark-800/50"
              >
                <MessageSquare size={16} className="text-dark-400" />
                <span className="truncate text-sm">{conv.title || '新对话'}</span>
              </div>
            ))}
            {searchResults?.results.length === 0 && (
              <div className="px-3 py-4 text-sm text-dark-400 text-center">
                未找到匹配的对话
              </div>
            )}
          </div>
        ) : (
          // Grouped Conversations
          <>
            {conversations?.pinned && conversations.pinned.length > 0 && (
              <ConversationGroup
                title="📌 置顶"
                conversations={conversations.pinned}
                defaultOpen={true}
              />
            )}
            <ConversationGroup
              title="今天"
              conversations={conversations?.today || []}
              defaultOpen={true}
            />
            <ConversationGroup
              title="昨天"
              conversations={conversations?.yesterday || []}
              defaultOpen={true}
            />
            <ConversationGroup
              title="本周"
              conversations={conversations?.this_week || []}
              defaultOpen={false}
            />
            <ConversationGroup
              title="更早"
              conversations={conversations?.earlier || []}
              defaultOpen={false}
            />
          </>
        )}
      </div>
      
      {/* Bottom Actions */}
      <div className="p-3 border-t border-dark-800">
        <button
          onClick={() => navigate('/settings')}
          className="sidebar-item w-full"
        >
          <Settings size={18} />
          <span>设置</span>
        </button>
      </div>
    </aside>
  )
}

