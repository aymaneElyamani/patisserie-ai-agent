export type MessageRole = 'user' | 'assistant' | 'system'

export interface MessageRead {
  role: MessageRole
  content: string
  id: number
  conversation_id: number
  created_at: string
}

export interface ConversationRead {
  title: string
  id: number
  created_at: string
  updated_at: string
}

export interface ConversationDetail extends ConversationRead {
  messages: MessageRead[]
}

export interface ConversationCreate {
  title?: string
}

export interface MessageCreate {
  role: MessageRole
  content: string
}

export interface ChatRequest {
  content: string
}

export interface ChatResponse {
  user_message: MessageRead
  assistant_message: MessageRead
}
