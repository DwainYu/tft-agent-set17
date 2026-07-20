from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from api.models.conversation import (
    ConversationCreate,
    ConversationOut,
    MessageCreate,
    MessageOut,
)
from api.services.conversation_svc import ConversationService
from api.database import get_db
from api.core.security import decode_token

router = APIRouter(prefix="/conversations", tags=["conversations"])

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Dependency: extract user_id from JWT Bearer token."""
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload["sub"]


# ------------------------------------------------------------------ routes


@router.get("", response_model=list[ConversationOut])
async def list_conversations(user_id: str = Depends(get_current_user)):
    """List all conversations for the current user."""
    with get_db() as conn:
        svc = ConversationService(conn)
        return svc.list_conversations(user_id)


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    user_id: str = Depends(get_current_user),
):
    """Create a new conversation."""
    with get_db() as conn:
        svc = ConversationService(conn)
        return svc.create_conversation(user_id, body.title)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get all messages in a conversation."""
    with get_db() as conn:
        svc = ConversationService(conn)
        convo = svc.get_conversation(conversation_id)
        if convo is None or convo.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return svc.list_messages(conversation_id)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    conversation_id: str,
    body: MessageCreate,
    user_id: str = Depends(get_current_user),
):
    """Add a message to a conversation."""
    with get_db() as conn:
        svc = ConversationService(conn)
        convo = svc.get_conversation(conversation_id)
        if convo is None or convo.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return svc.add_message(
            conversation_id, body.role, body.content, body.metadata
        )
