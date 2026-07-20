"""Conversation service – CRUD for conversations and messages."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


class ConversationService:
    """Manage conversations and their messages."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def create(self, user_id: int | None, title: str | None = None) -> dict:
        """Create a new conversation and return it as a dict."""
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO conversations (user_id, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, title, now, now),
        )
        self._conn.commit()
        conv_id = cur.lastrowid
        return {
            "id": conv_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }

    def list_by_user(self, user_id: int) -> list[dict]:
        """Return all conversations belonging to *user_id*, newest first."""
        cur = self._conn.execute(
            "SELECT id, title, created_at, updated_at "
            "FROM conversations "
            "WHERE user_id = ? "
            "ORDER BY updated_at DESC",
            (user_id,),
        )
        columns = ["id", "title", "created_at", "updated_at"]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> dict:
        """Add a message to *conversation_id* and return it."""
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

        cur = self._conn.execute(
            "INSERT INTO messages (conversation_id, role, content, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, metadata_json, now),
        )
        self._conn.commit()
        msg_id = cur.lastrowid

        # Bump the conversation's updated_at
        self._conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        self._conn.commit()

        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "created_at": now,
        }

    def get_messages(self, conversation_id: int) -> list[dict]:
        """Return all messages in *conversation_id* in chronological order."""
        cur = self._conn.execute(
            "SELECT id, conversation_id, role, content, created_at "
            "FROM messages "
            "WHERE conversation_id = ? "
            "ORDER BY created_at ASC",
            (conversation_id,),
        )
        columns = ["id", "conversation_id", "role", "content", "created_at"]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Aliases expected by routers
    # ------------------------------------------------------------------

    def list_conversations(self, user_id: str | int) -> list[dict]:
        return self.list_by_user(int(user_id))

    def create_conversation(self, user_id: str | int, title: str | None = None) -> dict:
        return self.create(int(user_id), title)

    def get_conversation(self, conversation_id: str | int) -> dict | None:
        cur = self._conn.execute(
            "SELECT id, user_id, title, created_at, updated_at "
            "FROM conversations WHERE id = ?",
            (int(conversation_id),),
        )
        row = cur.fetchone()
        if row is None:
            return None
        columns = ["id", "user_id", "title", "created_at", "updated_at"]
        return dict(zip(columns, row))

    def list_messages(self, conversation_id: str | int) -> list[dict]:
        return self.get_messages(int(conversation_id))
