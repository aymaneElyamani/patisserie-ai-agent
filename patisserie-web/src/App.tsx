import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from './api/client'
import { ChatWindow } from './components/ChatWindow'
import { ErrorBanner } from './components/ErrorBanner'
import { Sidebar } from './components/Sidebar'
import type { ConversationRead, MessageRead } from './types/api'
import './App.css'

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Une erreur inattendue est survenue.'
}

function App() {
  const [showSplash, setShowSplash] = useState(true)
  const [conversations, setConversations] = useState<ConversationRead[]>([])
  const [conversationsLoading, setConversationsLoading] = useState(true)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<MessageRead[]>([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [creating, setCreating] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const loadIdRef = useRef(0)

  useEffect(() => {
    const splashTimer = window.setTimeout(() => setShowSplash(false), 2500)
    return () => window.clearTimeout(splashTimer)
  }, [])

  const invalidatePendingLoads = useCallback(() => {
    loadIdRef.current += 1
  }, [])

  function handleHome() {
    invalidatePendingLoads()
    setActiveId(null)
    setMessages([])
    setError(null)
    setSidebarOpen(false)
  }

  const openConversation = useCallback(
    async (conversationId: number) => {
      const loadId = ++loadIdRef.current
      setActiveId(conversationId)
      setSidebarOpen(false)
      setMessagesLoading(true)
      setError(null)
      try {
        const history = await api.listMessages(conversationId)
        if (loadId !== loadIdRef.current) return
        setMessages(history)
      } catch (caught) {
        if (loadId !== loadIdRef.current) return
        setMessages([])
        setError(toErrorMessage(caught))
      } finally {
        if (loadId === loadIdRef.current) setMessagesLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const list = await api.listConversations()
        if (cancelled) return
        setConversations(list)
      } catch (caught) {
        if (!cancelled) setError(toErrorMessage(caught))
      } finally {
        if (!cancelled) setConversationsLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  async function handleCreate() {
    if (creating) return
    setCreating(true)
    setError(null)
    try {
      const conversation = await api.createConversation({})
      invalidatePendingLoads()
      setConversations((current) => [conversation, ...current])
      setActiveId(conversation.id)
      setMessages(conversation.messages)
      setSidebarOpen(false)
    } catch (caught) {
      setError(toErrorMessage(caught))
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(conversationId: number) {
    if (deletingId !== null) return
    setDeletingId(conversationId)
    setError(null)
    try {
      await api.deleteConversation(conversationId)
      const remaining = conversations.filter(
        (conversation) => conversation.id !== conversationId,
      )
      setConversations(remaining)

      if (conversationId === activeId) {
        invalidatePendingLoads()
        setActiveId(null)
        setMessages([])
        if (remaining.length > 0) {
          await openConversation(remaining[0].id)
        }
      }
    } catch (caught) {
      setError(toErrorMessage(caught))
    } finally {
      setDeletingId(null)
    }
  }

  async function handleSend(content: string) {
    if (sending) return
    if (activeId === null && creating) return
    setSending(true)
    setError(null)

    let targetId = activeId
    let sendLoadId = loadIdRef.current
    const tempId = -Date.now()

    try {
      if (targetId === null) {
        const conversation = await api.createConversation({})
        invalidatePendingLoads()
        setConversations((current) => [conversation, ...current])
        setActiveId(conversation.id)
        setMessages(conversation.messages)
        targetId = conversation.id
      }

      const conversationId = targetId
      sendLoadId = loadIdRef.current

      setMessages((current) => [
        ...current,
        {
          id: tempId,
          role: 'user',
          content,
          conversation_id: conversationId,
          created_at: new Date().toISOString(),
        },
      ])

      const response = await api.chat(conversationId, { content })
      if (sendLoadId !== loadIdRef.current) return
      setMessages((current) => [
        ...current.filter((message) => message.id !== tempId),
        response.user_message,
        response.assistant_message,
      ])
      setConversations((current) => {
        const updated = current.map((conversation) =>
          conversation.id === conversationId
            ? { ...conversation, updated_at: response.assistant_message.created_at }
            : conversation,
        )
        return [...updated].sort(
          (a, b) =>
            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
        )
      })
    } catch (caught) {
      if (sendLoadId === loadIdRef.current) {
        setMessages((current) =>
          current.filter((message) => message.id !== tempId),
        )
      }
      setError(toErrorMessage(caught))
    } finally {
      setSending(false)
    }
  }

  if (showSplash) {
    return (
      <div className="splash-screen" role="status" aria-label="Chargement de PâtissIA">
        <img
          className="splash-screen__image"
          src="/patissia.jpeg"
          alt="L'équipe PâtissIA dans sa pâtisserie"
        />
        <div className="splash-screen__overlay">
          <span className="splash-screen__brand">Pâtiss<span>IA</span></span>
          <span className="splash-screen__tagline">Votre assistant pâtisserie</span>
        </div>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <div className="app">
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          loading={conversationsLoading}
          creating={creating}
          deletingId={deletingId}
          open={sidebarOpen}
          onSelect={(conversationId) => void openConversation(conversationId)}
          onCreate={() => void handleCreate()}
          onDelete={(conversationId) => void handleDelete(conversationId)}
          onHome={handleHome}
          onClose={() => setSidebarOpen(false)}
        />

        <div className="app__main">
          {error ? <ErrorBanner message={error} onClose={() => setError(null)} /> : null}
          <ChatWindow
            messages={messages}
            loading={messagesLoading}
            sending={sending}
            onSend={(content) => void handleSend(content)}
          />
        </div>
      </div>
    </div>
  )
}

export default App
