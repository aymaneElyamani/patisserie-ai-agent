import { useRef, useState } from 'react'

interface ComposerProps {
  disabled: boolean
  onSend: (content: string) => void
}

const MAX_HEIGHT = 176

function SendIcon() {
  return (
    <svg
      className="composer__send-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 19V5" />
      <path d="m5 12 7-7 7 7" />
    </svg>
  )
}

export function Composer({ disabled, onSend }: ComposerProps) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLTextAreaElement | null>(null)

  function resize() {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }

  function submit() {
    const content = value.trim()
    if (!content || disabled) return
    onSend(content)
    setValue('')
    requestAnimationFrame(resize)
  }

  function handleChange(event: React.ChangeEvent<HTMLTextAreaElement>) {
    setValue(event.target.value)
    resize()
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <footer className="composer">
      <div className="composer__box">
        <textarea
          ref={inputRef}
          className="composer__input"
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Demandez quelque chose à votre assistant pâtisserie..."
          rows={1}
          maxLength={2000}
          disabled={disabled}
          aria-label="Votre message"
        />
        <button
          type="button"
          className="composer__send"
          onClick={submit}
          disabled={disabled || value.trim().length === 0}
          aria-label="Envoyer le message"
          title="Envoyer"
        >
          <SendIcon />
        </button>
      </div>
      <p className="composer__hint">
        PâtissIA peut faire des erreurs. Vérifiez les informations importantes.
      </p>
    </footer>
  )
}
