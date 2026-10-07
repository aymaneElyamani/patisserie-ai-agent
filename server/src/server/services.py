"""Conversation, message, recipe retrieval, and chatbot business logic."""

from pathlib import Path

from openai import OpenAIError
from server.env import IS_CSV_DATA_ACTIVE, OPENAI_MODEL, RECENT_MESSAGE_LIMIT
from sqlmodel import Session, delete, select

from .exceptions import ChatbotUnavailableError, ConversationNotFoundError
from .models import (
    ChatRequest,
    ChatResponse,
    Conversation,
    ConversationCreate,
    ConversationDetail,
    ConversationUpdate,
    Message,
    MessageCreate,
    MessageRole,
    utc_now,
)

from .agent import agentOpenAIClient

from .utils import build_recipe_context



INSTRUCTIONS_PATH = Path(__file__).resolve().parents[2] / "instructions.md"

DEFAULT_ASSISTANT_MESSAGE = (
    "<h2>Bienvenue chez Atelier Amande</h2>"
    "<p>Je peux vous aider avec une recette, une technique ou un problème "
    "de pâtisserie. Que souhaitez-vous préparer&nbsp;?</p>"
)


def load_chatbot_instructions() -> str:
    """Load the chatbot policy from the project instructions file."""
    instructions = INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()
    
    return instructions


class ConversationService:
    @staticmethod
    def create(session: Session, data: ConversationCreate) -> ConversationDetail:
        conversation = Conversation.model_validate(data)
        session.add(conversation)
        session.flush()

        welcome_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=DEFAULT_ASSISTANT_MESSAGE,
        )
        session.add(welcome_message)
        session.commit()
        session.refresh(conversation)
        session.refresh(welcome_message)
        return ConversationDetail(
            **conversation.model_dump(),
            messages=[welcome_message],
        )

    @staticmethod
    def get_all(
        session: Session,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Conversation]:
        statement = (
            select(Conversation)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(session.exec(statement).all())

    @staticmethod
    def get_by_id(session: Session, conversation_id: int) -> Conversation:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(
                f"Conversation {conversation_id} introuvable"
            )
        return conversation

    @staticmethod
    def get_detail(session: Session, conversation_id: int) -> ConversationDetail:
        conversation = ConversationService.get_by_id(session, conversation_id)
        messages = MessageService.get_by_conversation(session, conversation_id)
        return ConversationDetail(
            **conversation.model_dump(),
            messages=messages,
        )

    @staticmethod
    def update(
        session: Session,
        conversation_id: int,
        data: ConversationUpdate,
    ) -> Conversation:
        conversation = ConversationService.get_by_id(session, conversation_id)
        conversation.title = data.title
        conversation.updated_at = utc_now()
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        return conversation

    @staticmethod
    def delete(session: Session, conversation_id: int) -> None:
        conversation = ConversationService.get_by_id(session, conversation_id)
        session.exec(
            delete(Message).where(Message.conversation_id == conversation_id)
        )
        session.delete(conversation)
        session.commit()


class MessageService:
    @staticmethod
    def create(
        session: Session,
        conversation_id: int,
        data: MessageCreate,
    ) -> Message:
        conversation = ConversationService.get_by_id(session, conversation_id)
        message = Message(
            conversation_id=conversation_id,
            role=data.role,
            content=data.content,
        )
        conversation.updated_at = utc_now()
        session.add(message)
        session.add(conversation)
        session.commit()
        session.refresh(message)
        return message

    @staticmethod
    def get_by_conversation(
        session: Session,
        conversation_id: int,
    ) -> list[Message]:
        ConversationService.get_by_id(session, conversation_id)
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(session.exec(statement).all())


class ChatbotService:
    @staticmethod
    def generate_response(messages: list[Message], user_content: str) -> str:
        """Generate a contextual response using the configured AI provider."""
        
        conversation_input = [
            {"role": "system", "content": load_chatbot_instructions()},
        ]
        
        recipe_context = ""

        if IS_CSV_DATA_ACTIVE:
            recipe_context = build_recipe_context(user_content)

        if recipe_context:
            conversation_input.append(
                {
                    "role": "system",
                    "content": (
                        "Voici les recettes pertinentes extraites de la base locale. "
                        "Utilise ces données comme source principale. "
                        "N'invente pas de quantités ou d'étapes absentes.\n\n"
                        f"{recipe_context}"
                    ),
                }
            )
        conversation_input.extend(
            {"role": message.role.value, "content": message.content}
            for message in messages
        )
        conversation_input.append({"role": "user", "content": user_content})

        try:
            response = agentOpenAIClient.chat.completions.create(
                model= OPENAI_MODEL,
                messages=conversation_input,
                temperature=0.2,
            )
        except OpenAIError as error:
            raise ChatbotUnavailableError from error

        assistant_content = response.choices[0].message.content
        if not assistant_content or not assistant_content.strip():
            raise ChatbotUnavailableError("AI provider returned an empty response")
        return assistant_content.strip()
         
    @staticmethod
    def chat(
        session: Session,
        conversation_id: int,
        data: ChatRequest,
    ) -> ChatResponse:
        conversation = ConversationService.get_by_id(session, conversation_id)
        previous_messages = MessageService.get_by_conversation(
            session,
            conversation_id,
        )
        recent_messages = previous_messages[-RECENT_MESSAGE_LIMIT:]

        assistant_content = ChatbotService.generate_response(
            recent_messages,
            data.content,
        )

        # save the msgs in db
        user_message = MessageService.create(
            session,
            conversation.id,
            MessageCreate(role="user", content=data.content),
        )
        assistant_message = MessageService.create(
            session,
            conversation.id,
            MessageCreate(
                role="assistant",
                content=assistant_content,
            ),
        )

        return ChatResponse(
            user_message=user_message,
            assistant_message=assistant_message,
        )
