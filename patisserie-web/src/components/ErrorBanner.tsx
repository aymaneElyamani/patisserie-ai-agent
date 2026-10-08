interface ErrorBannerProps {
  message: string
  onClose: () => void
}

export function ErrorBanner({ message, onClose }: ErrorBannerProps) {
  return (
    <div className="error-banner" role="alert">
      <span className="error-banner__text">{message}</span>
      <button
        type="button"
        className="error-banner__close"
        onClick={onClose}
        aria-label="Fermer l'erreur"
      >
        ×
      </button>
    </div>
  )
}
