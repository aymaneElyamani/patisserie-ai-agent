"""Database entities and API schemas."""

from datetime import datetime, timezone
from enum import StrEnum

from sqlmodel import Field, SQLModel


DEFAULT_CONVERSATION_TITLE = "Nouvelle conversation"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


class ConversationBase(SQLModel):
    title: str = Field(min_length=1, max_length=30)


class Conversation(ConversationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ConversationCreate(SQLModel):
    title: str = Field(
        default=DEFAULT_CONVERSATION_TITLE,
        min_length=1,
        max_length=30,
    )


class ConversationRead(ConversationBase):
    id: int
    created_at: datetime
    updated_at: datetime


class ConversationUpdate(ConversationBase):
    pass


class MessageBase(SQLModel):
    role: MessageRole
    content: str = Field(min_length=1)


class Message(MessageBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(
        foreign_key="conversation.id",
        index=True,
    )
    created_at: datetime = Field(default_factory=utc_now)


class MessageCreate(MessageBase):
    pass


class MessageRead(MessageBase):
    id: int
    conversation_id: int
    created_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]


class ChatRequest(SQLModel):
    content: str = Field(min_length=1)


class ChatResponse(SQLModel):
    user_message: MessageRead
    assistant_message: MessageRead
    conversation_title: str
