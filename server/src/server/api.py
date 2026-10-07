"""HTTP routes for the chatbot API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session

from .database import get_session
from .exceptions import ChatbotUnavailableError, ConversationNotFoundError
from .models import (
    ChatRequest,
    ChatResponse,
    Conversation,
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    Message,
    MessageCreate,
    MessageRead,
)
from .services import (
    ChatbotService,
    ConversationService,
    MessageService,
)
router = APIRouter(prefix="/api", tags=["Chatbot"])
SessionDependency = Annotated[Session, Depends(get_session)]


def not_found(error: ConversationNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/conversations",
    response_model=ConversationDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    data: ConversationCreate,
    session: SessionDependency,
) -> ConversationDetail:
    return ConversationService.create(session, data)


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[Conversation]:
    return ConversationService.get_all(session, offset=offset, limit=limit)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
)
def get_conversation(
    conversation_id: int,
    session: SessionDependency,
) -> ConversationDetail:
    try:
        return ConversationService.get_detail(session, conversation_id)
    except ConversationNotFoundError as error:
        raise not_found(error) from error


# @router.put(
#     "/conversations/{conversation_id}",
#     response_model=ConversationRead,
# )
# def update_conversation(
#     conversation_id: int,
#     data: ConversationUpdate,
#     session: SessionDependency,
# ) -> Conversation:
#     try:
#         return ConversationService.update(session, conversation_id, data)
#     except ConversationNotFoundError as error:
#         raise not_found(error) from error



# Demande dans le TP
@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: int,
    session: SessionDependency,
) -> Response:
    try:
        ConversationService.delete(session, conversation_id)
    except ConversationNotFoundError as error:
        raise not_found(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageRead],
)
def list_messages(
    conversation_id: int,
    session: SessionDependency,
) -> list[Message]:
    try:
        return MessageService.get_by_conversation(session, conversation_id)
    except ConversationNotFoundError as error:
        raise not_found(error) from error


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    conversation_id: int,
    data: MessageCreate,
    session: SessionDependency,
) -> Message:
    try:
        return MessageService.create(session, conversation_id, data)
    except ConversationNotFoundError as error:
        raise not_found(error) from error



# Demande dans le TP
@router.post(
    "/conversations/{conversation_id}/chat",
    response_model=ChatResponse,
)
def chat(
    conversation_id: int,
    data: ChatRequest,
    session: SessionDependency,
) -> ChatResponse:
    try:
        return ChatbotService.chat(session, conversation_id, data)
    except ConversationNotFoundError as error:
        raise not_found(error) from error
    except ChatbotUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "L’assistant est temporairement indisponible. "
                "Vérifiez la configuration Groq puis réessayez."
            ),
        ) from error
