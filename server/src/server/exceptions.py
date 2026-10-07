"""Domain exceptions."""


class ConversationNotFoundError(Exception):
    """Raised when a requested conversation does not exist."""


class ChatbotUnavailableError(Exception):
    """Raised when the language model cannot generate a response."""
