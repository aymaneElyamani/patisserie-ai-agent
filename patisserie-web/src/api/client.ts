import type {
  ChatRequest,
  ChatResponse,
  ConversationCreate,
  ConversationDetail,
  ConversationRead,
  MessageCreate,
  MessageRead,
} from '../types/api'

const envUrl = (import.meta.env as { VITE_API_URL?: string }).VITE_API_URL

export const API_URL = (envUrl ?? 'http://127.0.0.1:8000').replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.json()
    if (payload && typeof payload === 'object' && 'detail' in payload) {
      const detail = (payload as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail)) {
        return detail
          .map((item) =>
            item && typeof item === 'object' && 'msg' in item
              ? String((item as { msg: unknown }).msg)
              : JSON.stringify(item),
          )
          .join(', ')
      }
      return JSON.stringify(detail)
    }
  } catch {
    // Le corps n'est pas du JSON exploitable.
  }
  return `Erreur ${response.status} ${response.statusText}`
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError(
      0,
      'Serveur injoignable. Vérifiez que l\'API est lancée sur ' + API_URL,
    )
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  return (text ? JSON.parse(text) : undefined) as T
}

function jsonBody(data: unknown): string {
  return JSON.stringify(data)
}

export const api = {
  listConversations(): Promise<ConversationRead[]> {
    return request<ConversationRead[]>('/api/conversations')
  },

  createConversation(data: ConversationCreate): Promise<ConversationDetail> {
    return request<ConversationDetail>('/api/conversations', {
      method: 'POST',
      body: jsonBody(data),
    })
  },

  getConversation(conversationId: number): Promise<ConversationDetail> {
    return request<ConversationDetail>(`/api/conversations/${conversationId}`)
  },

  deleteConversation(conversationId: number): Promise<void> {
    return request<void>(`/api/conversations/${conversationId}`, {
      method: 'DELETE',
    })
  },

  listMessages(conversationId: number): Promise<MessageRead[]> {
    return request<MessageRead[]>(`/api/conversations/${conversationId}/messages`)
  },

  createMessage(
    conversationId: number,
    data: MessageCreate,
  ): Promise<MessageRead> {
    return request<MessageRead>(`/api/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: jsonBody(data),
    })
  },

  chat(conversationId: number, data: ChatRequest): Promise<ChatResponse> {
    return request<ChatResponse>(`/api/conversations/${conversationId}/chat`, {
      method: 'POST',
      body: jsonBody(data),
    })
  },
}
