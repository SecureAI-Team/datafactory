import { create } from 'zustand'

// Interactive question types
export interface InteractionOption {
  id: string
  label: string
  icon?: string
  description?: string
}

export interface InteractionQuestion {
  id: string
  question: string
  type: 'single' | 'multiple' | 'input'
  options?: InteractionOption[]
  inputType?: 'text' | 'number' | 'date'
  placeholder?: string
  validation?: {
    min?: number
    max?: number
  }
  required?: boolean
}

export interface InteractionData {
  sessionId: string
  flowId: string
  flowName: string
  currentStep: number
  totalSteps: number
  question: InteractionQuestion
  collectedAnswers: Record<string, string | string[]>
}

// LLM 触发的交互流程信息
export interface InteractionTriggerInfo {
  flow_id: string
  flow_name: string
  description?: string
  confidence: number
  reason: string
}

export interface Message {
  id: number
  message_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  sources: Array<{ title: string; url?: string }>
  feedback: 'positive' | 'negative' | null
  tokens_used: number | null
  model_used: string | null
  latency_ms: number | null
  created_at: string
  // Interactive message data
  interaction?: InteractionData
  // LLM 智能触发的交互流程信息
  interaction_trigger?: InteractionTriggerInfo
}

export interface Conversation {
  id: number
  conversation_id: string
  title: string | null
  summary: string | null
  status: 'active' | 'archived' | 'deleted'
  is_pinned: boolean
  message_count: number
  last_message_at: string | null
  tags: string[]
  scenario_id: string | null
  created_at: string
  updated_at: string
}

interface ConversationGroups {
  pinned: Conversation[]
  today: Conversation[]
  yesterday: Conversation[]
  this_week: Conversation[]
  earlier: Conversation[]
}

interface ConversationState {
  conversations: ConversationGroups
  currentConversationId: string | null
  messages: Message[]
  isLoading: boolean
  isSending: boolean
  
  // Actions
  setConversations: (groups: ConversationGroups) => void
  setCurrentConversation: (id: string | null) => void
  setMessages: (messages: Message[]) => void
  addMessage: (message: Message) => void
  updateMessage: (messageId: string, updates: Partial<Message>) => void
  setLoading: (loading: boolean) => void
  setSending: (sending: boolean) => void
  addConversation: (conversation: Conversation) => void
  updateConversation: (id: string, updates: Partial<Conversation>) => void
  removeConversation: (id: string) => void
}

export const useConversationStore = create<ConversationState>((set) => ({
  conversations: {
    pinned: [],
    today: [],
    yesterday: [],
    this_week: [],
    earlier: [],
  },
  currentConversationId: null,
  messages: [],
  isLoading: false,
  isSending: false,
  
  setConversations: (groups) => set({ conversations: groups }),
  
  setCurrentConversation: (id) => set({ currentConversationId: id }),
  
  setMessages: (messages) => set({ messages }),
  
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message],
  })),
  
  updateMessage: (messageId, updates) => set((state) => ({
    messages: state.messages.map((m) =>
      m.message_id === messageId ? { ...m, ...updates } : m
    ),
  })),
  
  setLoading: (loading) => set({ isLoading: loading }),
  
  setSending: (sending) => set({ isSending: sending }),
  
  addConversation: (conversation) => set((state) => ({
    conversations: {
      ...state.conversations,
      today: [conversation, ...state.conversations.today],
    },
  })),
  
  updateConversation: (id, updates) => set((state) => {
    const updateInGroup = (group: Conversation[]) =>
      group.map((c) => (c.conversation_id === id ? { ...c, ...updates } : c))
    
    return {
      conversations: {
        pinned: updateInGroup(state.conversations.pinned),
        today: updateInGroup(state.conversations.today),
        yesterday: updateInGroup(state.conversations.yesterday),
        this_week: updateInGroup(state.conversations.this_week),
        earlier: updateInGroup(state.conversations.earlier),
      },
    }
  }),
  
  removeConversation: (id) => set((state) => {
    const filterGroup = (group: Conversation[]) =>
      group.filter((c) => c.conversation_id !== id)
    
    return {
      conversations: {
        pinned: filterGroup(state.conversations.pinned),
        today: filterGroup(state.conversations.today),
        yesterday: filterGroup(state.conversations.yesterday),
        this_week: filterGroup(state.conversations.this_week),
        earlier: filterGroup(state.conversations.earlier),
      },
    }
  }),
}))

