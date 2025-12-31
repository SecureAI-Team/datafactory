import apiClient from './client'
import { Conversation, Message } from '../store/conversationStore'

interface ConversationGroups {
  pinned: Conversation[]
  today: Conversation[]
  yesterday: Conversation[]
  this_week: Conversation[]
  earlier: Conversation[]
}

interface CreateConversationRequest {
  title?: string
  scenario_id?: string
}

interface UpdateConversationRequest {
  title?: string
  tags?: string[]
  scenario_id?: string
}

interface SendMessageRequest {
  content: string
}

interface FeedbackRequest {
  feedback: 'positive' | 'negative'
  feedback_text?: string
}

interface CreateShareRequest {
  allow_copy?: boolean
  expires_in_days?: number
}

interface ShareResponse {
  share_token: string
  share_url: string
  expires_at: string | null
}

interface SharedConversationResponse {
  conversation: Conversation
  messages: Message[]
  allow_copy: boolean
  shared_at: string
}

export const conversationsApi = {
  // Conversation CRUD
  list: async (): Promise<ConversationGroups> => {
    const response = await apiClient.get<ConversationGroups>('/api/conversations')
    return response.data
  },
  
  create: async (data?: CreateConversationRequest): Promise<Conversation> => {
    const response = await apiClient.post<Conversation>('/api/conversations', data || {})
    return response.data
  },
  
  get: async (conversationId: string): Promise<Conversation> => {
    const response = await apiClient.get<Conversation>(`/api/conversations/${conversationId}`)
    return response.data
  },
  
  update: async (conversationId: string, data: UpdateConversationRequest): Promise<Conversation> => {
    const response = await apiClient.put<Conversation>(`/api/conversations/${conversationId}`, data)
    return response.data
  },
  
  delete: async (conversationId: string): Promise<void> => {
    await apiClient.delete(`/api/conversations/${conversationId}`)
  },
  
  archive: async (conversationId: string): Promise<Conversation> => {
    const response = await apiClient.post<Conversation>(`/api/conversations/${conversationId}/archive`)
    return response.data
  },
  
  pin: async (conversationId: string, pinned: boolean): Promise<Conversation> => {
    const response = await apiClient.post<Conversation>(
      `/api/conversations/${conversationId}/pin?pinned=${pinned}`
    )
    return response.data
  },
  
  search: async (query: string): Promise<{ results: Conversation[] }> => {
    const response = await apiClient.get<{ results: Conversation[] }>(
      `/api/conversations/search?q=${encodeURIComponent(query)}`
    )
    return response.data
  },
  
  // Messages
  getMessages: async (conversationId: string): Promise<{ messages: Message[] }> => {
    const response = await apiClient.get<{ messages: Message[] }>(
      `/api/conversations/${conversationId}/messages`
    )
    return response.data
  },
  
  sendMessage: async (conversationId: string, data: SendMessageRequest): Promise<Message> => {
    const response = await apiClient.post<Message>(
      `/api/conversations/${conversationId}/messages`,
      data
    )
    return response.data
  },
  
  updateFeedback: async (
    conversationId: string,
    messageId: string,
    data: FeedbackRequest
  ): Promise<void> => {
    await apiClient.put(
      `/api/conversations/${conversationId}/messages/${messageId}/feedback`,
      data
    )
  },
  
  // Sharing
  createShare: async (conversationId: string, data?: CreateShareRequest): Promise<ShareResponse> => {
    const response = await apiClient.post<ShareResponse>(
      `/api/conversations/${conversationId}/share`,
      data || {}
    )
    return response.data
  },
  
  deleteShare: async (conversationId: string): Promise<void> => {
    await apiClient.delete(`/api/conversations/${conversationId}/share`)
  },
  
  getShared: async (token: string): Promise<SharedConversationResponse> => {
    const response = await apiClient.get<SharedConversationResponse>(
      `/api/conversations/share/${token}`
    )
    return response.data
  },
  
  // Export conversation
  export: async (conversationId: string, format: 'markdown' | 'pdf' = 'markdown'): Promise<{ content: string; filename: string }> => {
    try {
      const response = await apiClient.get<{ content: string; filename: string }>(
        `/api/conversations/${conversationId}/export?format=${format}`
      )
      return response.data
    } catch {
      // Fallback: generate markdown locally if API not available
      const messagesResponse = await apiClient.get<{ messages: Message[] }>(
        `/api/conversations/${conversationId}/messages`
      )
      const messages = messagesResponse.data.messages || []
      const content = messages.map(m => {
        const role = m.role === 'user' ? '**用户**' : '**助手**'
        return `${role}\n\n${m.content}\n\n---\n`
      }).join('\n')
      return {
        content: `# 对话导出\n\n导出时间: ${new Date().toLocaleString()}\n\n---\n\n${content}`,
        filename: `conversation-${conversationId}.md`
      }
    }
  },
}

