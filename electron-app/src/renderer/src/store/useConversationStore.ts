import { defineStore } from 'pinia'

export interface ChatMessage {
  id: string
  role: 'ai' | 'user'
  text: string
}

export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: ChatMessage[]
}

interface ConversationState {
  activeConversationId: string
  conversations: Conversation[]
}

const DEFAULT_TITLE = '新对话'
const WELCOME_MESSAGE = '您好。我已准备就绪，可以协助您处理今天的任务。请随时开始对话。'

const createId = (prefix: string): string => {
  const cryptoApi = globalThis.crypto
  if (cryptoApi && typeof cryptoApi.randomUUID === 'function') {
    return `${prefix}-${cryptoApi.randomUUID()}`
  }

  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

const createMessage = (role: ChatMessage['role'], text: string): ChatMessage => ({
  id: createId('msg'),
  role,
  text
})

const createConversationRecord = (): Conversation => {
  const now = new Date().toISOString()

  return {
    id: createId('conversation'),
    title: DEFAULT_TITLE,
    createdAt: now,
    updatedAt: now,
    messages: [createMessage('ai', WELCOME_MESSAGE)]
  }
}

const createConversationTitle = (text: string): string => {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (!normalized) {
    return DEFAULT_TITLE
  }

  return normalized.length > 18 ? `${normalized.slice(0, 18)}...` : normalized
}

const sortByUpdatedAtDesc = (conversations: Conversation[]): Conversation[] =>
  [...conversations].sort(
    (first, second) =>
      new Date(second.updatedAt).getTime() - new Date(first.updatedAt).getTime()
  )

export const useConversationStore = defineStore('conversationId', {
  state: (): ConversationState => ({
    activeConversationId: '',
    conversations: []
  }),
  getters: {
    sortedConversations(state): Conversation[] {
      return sortByUpdatedAtDesc(state.conversations)
    },
    activeConversation(state): Conversation | null {
      return (
        state.conversations.find(
          (conversation) => conversation.id === state.activeConversationId
        ) || null
      )
    },
    activeMessages(state): ChatMessage[] {
      const conversation = state.conversations.find(
        (item) => item.id === state.activeConversationId
      )

      return conversation?.messages || []
    }
  },
  actions: {
    ensureConversation(): string {
      const currentConversation = this.conversations.find(
        (conversation) => conversation.id === this.activeConversationId
      )
      if (currentConversation) {
        return currentConversation.id
      }

      const latestConversation = sortByUpdatedAtDesc(this.conversations)[0]
      if (latestConversation) {
        this.activeConversationId = latestConversation.id
        return latestConversation.id
      }

      const conversation = createConversationRecord()
      this.conversations.unshift(conversation)
      this.activeConversationId = conversation.id
      return conversation.id
    },
    createConversation(): string {
      const conversation = createConversationRecord()
      this.conversations.unshift(conversation)
      this.activeConversationId = conversation.id
      return conversation.id
    },
    selectConversation(conversationId: string): boolean {
      const conversation = this.conversations.find((item) => item.id === conversationId)
      if (!conversation) {
        return false
      }

      this.activeConversationId = conversation.id
      return true
    },
    appendMessage(role: ChatMessage['role'], text: string): ChatMessage {
      const conversationId = this.ensureConversation()
      const conversation = this.conversations.find((item) => item.id === conversationId)

      if (!conversation) {
        throw new Error('Active conversation is missing.')
      }

      const message = createMessage(role, text)
      conversation.messages.push(message)
      conversation.updatedAt = new Date().toISOString()

      if (role === 'user' && conversation.title === DEFAULT_TITLE) {
        conversation.title = createConversationTitle(text)
      }

      return message
    },
    updateMessageText(messageId: string, text: string, conversationId?: string): void {
      const conversation =
        this.conversations.find((item) => item.id === (conversationId || this.activeConversationId)) ||
        this.conversations.find((item) =>
          item.messages.some((message) => message.id === messageId)
        )
      if (!conversation) {
        return
      }

      const target = conversation.messages.find((message) => message.id === messageId)
      if (!target) {
        return
      }

      target.text = text
      conversation.updatedAt = new Date().toISOString()
    }
  },
  persist: {
    enabled: true,
    strategies: [
      {
        storage: localStorage,
        paths: ['activeConversationId', 'conversations']
      }
    ]
  }
})
