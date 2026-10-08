import type { MessageRead } from '../types/api'
import { sanitizeHtml } from '../utils/sanitize'

interface MessageBubbleProps {
  message: MessageRead
}

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  const content = (
    <div className="message__content">
      <div className="message__meta">
        <span className="message__author">
          {isUser ? 'Vous' : 'Atelier Amande'}
        </span>
        <time className="message__time" dateTime={message.created_at}>
          {formatTime(message.created_at)}
        </time>
      </div>
      <div className="message__bubble">
        {isUser ? (
          <p className="message__text">{message.content}</p>
        ) : (
          <div
            className="message__html"
            dangerouslySetInnerHTML={{ __html: sanitizeHtml(message.content) }}
          />
        )}
      </div>
    </div>
  )

  return (
    <article
      className={`message message--${isUser ? 'user' : 'assistant'}`}
      aria-label={isUser ? 'Votre message' : 'Réponse de Atelier Amande'}
    >
      {isUser ? (
        content
      ) : (
        <>
          <span className="message__avatar" aria-hidden="true">
            A
          </span>
          {content}
        </>
      )}
    </article>
  )
}
