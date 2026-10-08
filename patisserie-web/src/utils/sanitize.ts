import DOMPurify from 'dompurify'

const ALLOWED_TAGS = [
  'h2',
  'h3',
  'p',
  'ul',
  'ol',
  'li',
  'strong',
  'em',
  'br',
  'blockquote',
  'figure',
  'figcaption',
  'img',
]

const ALLOWED_ATTR = ['src', 'alt']

const ALLOWED_URI_REGEXP = /^https:\/\/.+/i

export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOWED_URI_REGEXP,
  })
}
