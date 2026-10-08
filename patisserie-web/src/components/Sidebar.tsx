import { useState } from 'react'
import type { ConversationRead } from '../types/api'
import { Spinner } from './Spinner'

interface SidebarProps {
  conversations: ConversationRead[]
  activeId: number | null
  loading: boolean
  creating: boolean
  deletingId: number | null
  open: boolean
  onSelect: (conversationId: number) => void
  onCreate: () => void
  onDelete: (conversationId: number) => void
  onHome: () => void
  onClose: () => void
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

interface ConversationItemProps {
  conversation: ConversationRead
  active: boolean
  deleting: boolean
  onSelect: () => void
  onDelete: () => void
}

function ConversationItem({
  conversation,
  active,
  deleting,
  onSelect,
  onDelete,
}: ConversationItemProps) {
  const [confirming, setConfirming] = useState(false)

  function handleDelete(event: React.MouseEvent) {
    event.stopPropagation()
    if (confirming) {
      onDelete()
      setConfirming(false)
      return
    }
    setConfirming(true)
  }

  return (
    <li
      className={`conversation-item${active ? ' conversation-item--active' : ''}`}
    >
      <button
        type="button"
        className="conversation-item__select"
        onClick={onSelect}
        aria-current={active ? 'true' : undefined}
      >
        <span className="conversation-item__title">{conversation.title}</span>
        <span className="conversation-item__date">
          {formatDate(conversation.updated_at)}
        </span>
      </button>
      <button
        type="button"
        className={`conversation-item__delete${
          confirming ? ' conversation-item__delete--confirming' : ''
        }`}
        onClick={handleDelete}
        onBlur={() => setConfirming(false)}
        disabled={deleting}
        aria-label={
          confirming
            ? `Confirmer la suppression de ${conversation.title}`
            : `Supprimer ${conversation.title}`
        }
        title={confirming ? 'Confirmer' : 'Supprimer'}
      >
        {deleting ? <Spinner /> : confirming ? 'OK' : '×'}
      </button>
    </li>
  )
}

export function Sidebar({
  conversations,
  activeId,
  loading,
  creating,
  deletingId,
  open,
  onSelect,
  onCreate,
  onDelete,
  onHome,
  onClose,
}: SidebarProps) {
  return (
    <>
      <div
        className={`sidebar-backdrop${open ? ' sidebar-backdrop--visible' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside className={`sidebar${open ? ' sidebar--open' : ''}`}>
        <header className="sidebar__header">
          <button
            type="button"
            className="sidebar__identity"
            onClick={onHome}
            aria-label="Retourner à l'accueil"
          >
            <span className="brand-badge" aria-hidden="true">
              ✦
            </span>
            <div>
              <p className="sidebar__brand">Pâtiss<span>IA</span></p>
            </div>
          </button>
          <button
            type="button"
            className="sidebar__close"
            onClick={onClose}
            aria-label="Fermer le menu"
          >
            ×
          </button>
        </header>

        <button
          type="button"
          className="sidebar__create"
          onClick={onCreate}
          disabled={creating}
        >
          <span className="sidebar__create-plus" aria-hidden="true">
            +
          </span>
          {creating ? 'Création…' : 'Nouvelle conversation'}
        </button>

        <div className="sidebar__search">⌕ <span>Rechercher</span><kbd>⌘ K</kbd></div>
        <p className="sidebar__section-label">Aujourd’hui</p>

        <nav className="sidebar__nav" aria-label="Conversations">
          {loading ? (
            <Spinner label="Chargement des conversations…" />
          ) : conversations.length === 0 ? (
            <p className="sidebar__empty">
              Aucune conversation pour le moment. Créez la première pour
              discuter avec pâtissIA.
            </p>
          ) : (
            <ul className="conversation-list">
              {conversations.map((conversation) => (
                <ConversationItem
                  key={conversation.id}
                  conversation={conversation}
                  active={conversation.id === activeId}
                  deleting={deletingId === conversation.id}
                  onSelect={() => onSelect(conversation.id)}
                  onDelete={() => onDelete(conversation.id)}
                />
              ))}
            </ul>
          )}
        </nav>

        <footer className="sidebar__footer">pâtissIA · Recettes &amp; techniques</footer>
      </aside>
    </>
  )
}
