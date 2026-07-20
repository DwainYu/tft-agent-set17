from __future__ import annotations

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationOut(BaseModel):
    id: int
    title: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MessageCreate(BaseModel):
    role: str
    content: str
    metadata: dict | None = None


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: str | None = None
