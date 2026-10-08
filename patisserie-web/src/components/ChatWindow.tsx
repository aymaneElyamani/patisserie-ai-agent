import { useEffect, useRef } from 'react'
import type { MessageRead } from '../types/api'
import { Composer } from './Composer'
import { MessageBubble } from './MessageBubble'
import { Spinner } from './Spinner'

interface ChatWindowProps {
  messages: MessageRead[]
  loading: boolean
  sending: boolean
  onSend: (content: string) => void
}

const SUGGESTIONS = [
  ['RECETTES', 'Donne-moi une recette de Paris-Brest', '▤'],
  ['TECHNIQUES', 'Comment réussir une pâte feuilletée ?', '♢'],
  ['CALCULS', 'Adapte cette recette pour 12 personnes', '▦'],
  ['DÉPANNAGE', 'Pourquoi ma ganache est-elle trop liquide ?', '△'],
]

function Welcome({
  disabled,
  onPick,
}: {
  disabled: boolean
  onPick: (suggestion: string) => void
}) {
  return (
    <div className="welcome">
      <span className="welcome__chef" aria-hidden="true">♨</span>
      <p className="welcome__eyebrow">VOTRE CHEF PÂTISSIER PERSONNEL</p>
      <h1 className="welcome__title">Bonjour 👋</h1>
      <p className="welcome__question">Que souhaitez-vous préparer aujourd’hui ?</p>
      <p className="welcome__text">Votre assistant IA spécialisé en pâtisserie.</p>
      <div className="suggestions">
        {SUGGESTIONS.map(([title, description, icon]) => (
          <button
            key={title}
            type="button"
            className="suggestion"
            onClick={() => onPick(description)}
            disabled={disabled}
          >
            <span className="suggestion__icon" aria-hidden="true">{icon}</span>
            <span><strong>{title}</strong><small>{description}</small></span>
            <span className="suggestion__arrow" aria-hidden="true">›</span>
          </button>
        ))}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="typing" role="status" aria-live="polite">
      <span className="message__avatar typing__avatar" aria-hidden="true">
        ✦
      </span>
      <div className="typing__bubble">
        <span className="typing__dot" aria-hidden="true" />
        <span className="typing__dot" aria-hidden="true" />
        <span className="typing__dot" aria-hidden="true" />
      </div>
      <span className="typing__label">Atelier Amande rédige sa réponse…</span>
    </div>
  )
}

export function ChatWindow({
  messages,
  loading,
  sending,
  onSend,
}: ChatWindowProps) {
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, loading, sending])

  const showWelcome = !loading && messages.length === 0

  return (
    <main className="chat">
      <section className="chat__messages" aria-live="polite">
        {loading ? (
          <div className="chat__loading">
            <Spinner label="Chargement de l'historique…" />
          </div>
        ) : showWelcome ? (
          <>
            <Welcome disabled={sending} onPick={onSend} />
            {sending ? <TypingIndicator /> : null}
          </>
        ) : (
          <div className="chat__messages-inner">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {sending ? <TypingIndicator /> : null}
          </div>
        )}
        <div ref={endRef} />
      </section>

      <Composer disabled={sending || loading} onSend={onSend} />
    </main>
  )
}
